#!/usr/bin/env python3
"""
Simple Prime Radiant V2 Smoke Test
Feature-Key: bd-6sk8.6
"""

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path

async def run_smoke_test():
    """Run basic Prime Radiant V2 smoke tests."""
    
    # Create reports directory
    reports_dir = Path("/tmp/prime-wave-reports")
    reports_dir.mkdir(parents=True, exist_ok=True)
    
    # Test results
    results = []
    
    try:
        # Import playwright
        from playwright.async_api import async_playwright
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page(viewport={"width": 1280, "height": 800})
            
            # Test 1: Load cockpit shell
            print("🚀 Starting Prime Radiant V2 smoke test...")
            print("1. Loading cockpit shell...")
            
            start_time = datetime.now()
            await page.goto("https://frontend-dev-f8a3.up.railway.app/v2")
            await page.wait_for_selector(".cockpit-shell", timeout=10000)
            await page.wait_for_selector(".chat-container", timeout=5000)
            
            # Take screenshot
            screenshot_path = reports_dir / "cockpit_load.png"
            await page.screenshot(path=str(screenshot_path))
            
            results.append({
                "story_id": "pr_v2_01_cockpit_load",
                "name": "Cockpit Shell Load",
                "status": "PASSED",
                "duration": (datetime.now() - start_time).total_seconds(),
                "screenshot": str(screenshot_path),
                "notes": "Cockpit shell loaded successfully"
            })
            
            print("✅ Cockpit shell loaded")
            
            # Test 2: Composer chat flow
            print("2. Testing composer chat flow...")
            start_time = datetime.now()
            
            composer_input = await page.wait_for_selector(".composer-input", timeout=5000)
            await composer_input.fill("Test message for advisor chat")
            
            send_button = await page.wait_for_selector(".send-button", timeout=3000)
            await send_button.click()
            
            await page.wait_for_selector(".message-bubble.thinking", timeout=10000)
            
            screenshot_path = reports_dir / "composer_chat.png"
            await page.screenshot(path=str(screenshot_path))
            
            results.append({
                "story_id": "pr_v2_02_composer_chat",
                "name": "Composer Chat Flow",
                "status": "PASSED",
                "duration": (datetime.now() - start_time).total_seconds(),
                "screenshot": str(screenshot_path),
                "notes": "Message sent and thinking state appeared"
            })
            
            print("✅ Composer chat flow completed")
            
            # Test 3: First assistant response
            print("3. Validating first assistant response...")
            start_time = datetime.now()
            
            await page.wait_for_selector(".message-bubble.answer", timeout=15000)
            
            # Check for evidence/provenance
            evidence_selector = await page.query_selector(".evidence-provenance")
            has_evidence = evidence_selector is not None
            
            screenshot_path = reports_dir / "first_response.png"
            await page.screenshot(path=str(screenshot_path))
            
            results.append({
                "story_id": "pr_v2_03_first_response",
                "name": "First Assistant Response",
                "status": "PASSED",
                "duration": (datetime.now() - start_time).total_seconds(),
                "screenshot": str(screenshot_path),
                "notes": f"Answer appeared, evidence available: {has_evidence}",
                "evidence_available": has_evidence
            })
            
            print("✅ First assistant response validated")
            
            await browser.close()
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        results.append({
            "story_id": "pr_v2_smoke_test",
            "name": "Smoke Test",
            "status": "FAILED",
            "error": str(e),
            "notes": "Fatal error during smoke test execution"
        })
    
    # Generate reports
    report_data = {
        "run_id": "bd-6sk8.6-dev-smoke",
        "start_time": datetime.now().isoformat(),
        "results": results,
        "summary": {
            "total": len(results),
            "passed": sum(1 for r in results if r.get("status") == "PASSED"),
            "failed": sum(1 for r in results if r.get("status") == "FAILED"),
            "success_rate": (sum(1 for r in results if r.get("status") == "PASSED") / len(results) * 100) if results else 0
        }
    }
    
    # Save markdown report
    markdown_path = reports_dir / "bd-6sk8.6-dev-smoke-report.md"
    with open(markdown_path, "w") as f:
        f.write("# Prime Radiant V2 Smoke Test Report\n\n")
        f.write(f"**Run ID**: {report_data['run_id']}\n")
        f.write(f"**Date**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("---\n\n")
        f.write("## Summary\n\n")
        f.write(f"✅ **Passed**: {report_data['summary']['passed']}/{report_data['summary']['total']}\n")
        f.write(f"❌ **Failed**: {report_data['summary']['failed']}\n")
        f.write(f"📊 **Success Rate**: {report_data['summary']['success_rate']:.1f}%\n\n")
        
        f.write("## Test Results\n\n")
        for result in results:
            status = "✅" if result.get("status") == "PASSED" else "❌"
            f.write(f"### {result['story_id']} {status}\n\n")
            f.write(f"**{result['name']}**\n\n")
            f.write(f"- Status: {result.get('status', 'UNKNOWN')}\n")
            f.write(f"- Duration: {result.get('duration', 0):.2f}s\n")
            if result.get("screenshot"):
                f.write(f"![{result['name']}](../{result['screenshot']})\n\n")
            if result.get("notes"):
                f.write(f"- Notes: {result['notes']}\n\n")
            if result.get("error"):
                f.write(f"- Error: `{result['error']}`\n\n")
    
    # Save JSON summary
    json_path = reports_dir / "bd-6sk8.6-dev-smoke-summary.json"
    with open(json_path, "w") as f:
        json.dump(report_data, f, indent=2)
    
    print(f"\n📊 Test completed. Reports generated:")
    print(f"   Markdown: {markdown_path}")
    print(f"   JSON: {json_path}")
    
    # Determine overall status
    passed = report_data['summary']['passed']
    total = report_data['summary']['total']
    
    if passed == total and total > 0:
        status = "PASS"
    elif passed >= total * 0.7:  # 70% pass rate
        status = "CONDITIONAL_PASS"
    else:
        status = "FAIL"
    
    print(f"\n🎯 QA_PRE_GATE={status}")
    
    return status, results

if __name__ == "__main__":
    asyncio.run(run_smoke_test())