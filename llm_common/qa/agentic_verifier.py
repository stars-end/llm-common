import base64
import os

from litellm import completion
from pydantic import BaseModel, Field


class VerificationResult(BaseModel):
    status: str = Field(..., description="PASS or FAIL")
    reasoning: str = Field(..., description="Explanation of the verdict")

class AgenticVerifier:
    """
    A verifier that uses VLM (Vision Language Models) to semantically valid UI states
    against user stories.
    """
    def __init__(self, model: str = "openai/glm-4.6v", temperature: float = 0.1):
        self.model = model
        self.temperature = temperature
        self.api_base = "https://api.z.ai/api/coding/paas/v4"
        self.api_key = os.environ.get("ZAI_API_KEY")

    def _encode_image(self, image_path: str) -> str:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')

    def verify(self, screenshot_path: str, story: str) -> VerificationResult:
        """
        Verifies a screenshot against a user story.
        """
        if not os.path.exists(screenshot_path):
            return VerificationResult(status="FAIL", reasoning=f"Screenshot not found at {screenshot_path}")

        base64_image = self._encode_image(screenshot_path)

        # Prepare messages for VLM
        messages = [
            {
                "role": "system",
                "content": "You are a QA Verification Agent. Your job is to strictly verify if a UI screenshot matches a User Story. Return PASS only if all criteria are met. Return FAIL if any error messages (like 500, 404, 'Unable to load') are visible or if requirements are missing. Be strict."
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": f"User Story to Verify:\n{story}\n\nAssess the screenshot:"},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{base64_image}"
                        },
                    },
                ],
            }
        ]

        try:
            response = completion(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                api_base=self.api_base,
                api_key=self.api_key,
                response_format=VerificationResult
            )

            # Extract structured response
            result_json = response.choices[0].message.content
            # LiteLLM/Instructor integration usually returns the object directly if response_format is used properly with some providers,
            # but GLM-4.6v via OpenAI proxy might return string JSON.
            # Let's rely on JSON parsing if it's a string.
            import json
            try:
                # Naive cleanup if markdown code blocks are present
                clean_json = result_json.replace("```json", "").replace("```", "").strip()
                data = json.loads(clean_json)
                return VerificationResult(**data)
            except Exception as e:
                # Fallback: Check for simple PASS/FAIL strings if JSON fails
                clean_response = result_json.strip().upper()
                if "PASS" in clean_response and len(clean_response) < 50:
                    return VerificationResult(status="PASS", reasoning="Model returned PASS without JSON.")
                if "FAIL" in clean_response and len(clean_response) < 50:
                    return VerificationResult(status="FAIL", reasoning=f"Model returned FAIL. Raw output: {result_json}")

                return VerificationResult(status="FAIL", reasoning=f"Model output parse error: {str(e)}. Raw output: {result_json}")

        except Exception as e:
            return VerificationResult(status="FAIL", reasoning=f"VLM Execution Error: {str(e)}")
