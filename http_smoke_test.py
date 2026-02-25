#!/usr/bin/env python3
"""
HTTP-based Prime Radiant V2 Smoke Test
Feature-Key: bd-6sk8.6
"""

import requests
import json
import os
from datetime import datetime
from pathlib import Path

def run_http_smoke_test():
    """Run basic HTTP-based Prime Radiant V2 smoke tests."""
    
    # Create reports directory
    reports_dir = Path("/tmp/prime-wave-reports")
    reports_dir.mkdir(parents=True, exist_ok=True)
    
    # Test results
    results = []
    
    try:
        # Test 1: Load frontend
        print("🚀 Starting Prime Radiant V2 HTTP smoke test...")
        print("1. Loading frontend...")
        
        start_time = datetime.now()
        response = requests.get("https://frontend-dev-f8a3.up.railway.app/v2", timeout=30)
        response.raise_for_status()
        
        results.append({
            "story_id": "pr_v2_01_frontend_load",
            "name": "Frontend Load",
            "status": "PASSED",
            "duration": (datetime.now() - start_time).total_seconds(),
            "http_status": response.status_code,
            "content_type": response.headers.get('content-type', ''),
            "notes": "Frontend loaded successfully"
        })
        
        print(f"✅ Frontend loaded (status: {response.status_code})")
        
        # Test 2: Check backend health
        print("2. Checking backend health...")
        start_time = datetime.now()
        
        response = requests.get("https://backend-dev-6dd5.up.railway.app/health", timeout=30)
        response.raise_for_status()
        
        results.append({
            "story_id": "pr_v2_02_backend_health",
            "name": "Backend Health",
            "status": "PASSED",
            "duration": (datetime.now() - start_time).total_seconds(),
            "http_status": response.status_code,
            "content_type": response.headers.get('content-type', ''),
            "notes": "Backend health check passed"
        })
        
        print(f"✅ Backend health check passed (status: {response.status_code})")
        
        # Test 3: Basic chat endpoint
        print("3. Testing basic chat endpoint...")
        start_time = datetime.now()
        
        chat_payload = {
            "message": "test message",
            "session_id": "smoke-test-session"
        }
        
        response = requests.post(
            "https://backend-dev-6dd5.up.railway.app/chat",
            json=chat_payload,
            timeout=60
        )
        response.raise_for_status()
        
        results.append({
            "story_id": "pr_v2_03_chat_endpoint",
            "name": "Chat Endpoint",
            "status": "PASSED",
            "duration": (datetime.now() - start_time).total_seconds(),
            "http_status": response.status_code,
            "content_type": response.headers.get('content-type', ''),
            "notes": "Chat endpoint responded successfully"
        })
        
        print(f"✅ Chat endpoint responded (status: {response.status_code})")
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Test failed: {e}")
        results.append({
            "story_id": "pr_v2_smoke_test",
            "name": "Smoke Test",
            "status": "FAILED",
            "error": str(e),
            "notes": "HTTP request failed during smoke test"
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
            if result.get("http_status"):
                f.write(f"- HTTP Status: {result['http_status']}\n")
            if result.get("content_type"):
                f.write(f"- Content-Type: {result['content_type']}\n")
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
    run_http_smoke_test()