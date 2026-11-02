#!/usr/bin/env python3
"""
SocialApp E2E Test Suite Runner
Executes requirement-driven opaque-box tests across 4 Tiers with rich reporting and filtering.
"""

import argparse
import json
import os
import sys
import time
import unittest
from typing import Dict, List, Optional, Tuple

# Ensure project root is in sys.path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "../.."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from tests.e2e.test_tier1_features import TestTier1Features
from tests.e2e.test_tier2_boundaries import TestTier2Boundaries
from tests.e2e.test_tier3_journeys import TestTier3Journeys
from tests.e2e.test_tier4_scenarios import TestTier4Scenarios


class TestReportResult(unittest.TestResult):
    """Custom test result tracking test execution times and tier stats."""

    def __init__(self):
        super().__init__()
        self.test_records = []
        self._start_time = None

    def startTest(self, test):
        super().startTest(test)
        self._start_time = time.time()

    def addSuccess(self, test):
        super().addSuccess(test)
        elapsed = time.time() - self._start_time if self._start_time else 0.0
        self.test_records.append({
            "test": str(test),
            "status": "PASS",
            "time": elapsed,
            "error": None,
        })

    def addFailure(self, test, err):
        super().addFailure(test, err)
        elapsed = time.time() - self._start_time if self._start_time else 0.0
        self.test_records.append({
            "test": str(test),
            "status": "FAIL",
            "time": elapsed,
            "error": self._exc_info_to_string(err, test),
        })

    def addError(self, test, err):
        super().addError(test, err)
        elapsed = time.time() - self._start_time if self._start_time else 0.0
        self.test_records.append({
            "test": str(test),
            "status": "ERROR",
            "time": elapsed,
            "error": self._exc_info_to_string(err, test),
        })

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self.test_records.append({
            "test": str(test),
            "status": "SKIP",
            "time": 0.0,
            "error": reason,
        })


def check_backend_reachability(base_url: str) -> bool:
    """Verifies whether the target backend is currently reachable."""
    try:
        from tests.e2e.test_client import ApiClient
        client = ApiClient(base_url=base_url, timeout=2.0)
        resp = client.get("/auth/me")
        # 401 Unauthorized means backend is up and running SecurityConfig
        return resp.status_code in (200, 401, 403, 404)
    except Exception:
        return False


def build_suite(tier: str, feature_filter: Optional[str] = None) -> unittest.TestSuite:
    """Builds test suite based on tier selection and optional feature filter."""
    suite = unittest.TestSuite()
    tier_map = {
        "1": [TestTier1Features],
        "2": [TestTier2Boundaries],
        "3": [TestTier3Journeys],
        "4": [TestTier4Scenarios],
        "all": [TestTier1Features, TestTier2Boundaries, TestTier3Journeys, TestTier4Scenarios],
    }

    classes = tier_map.get(tier.lower(), tier_map["all"])

    for test_class in classes:
        loader = unittest.TestLoader()
        test_names = loader.getTestCaseNames(test_class)
        for name in test_names:
            if feature_filter:
                if feature_filter.lower() not in name.lower():
                    continue
            suite.addTest(test_class(name))

    return suite


def main():
    parser = argparse.ArgumentParser(description="SocialApp E2E Test Suite Runner")
    parser.add_argument(
        "--tier",
        choices=["all", "1", "2", "3", "4"],
        default="all",
        help="Tier selection to run: 1 (Features), 2 (Boundaries), 3 (Journeys), 4 (Scenarios), or all",
    )
    parser.add_argument(
        "--base-url",
        default=os.environ.get("BASE_URL", "http://localhost:8080/api"),
        help="Backend REST API base URL (default: http://localhost:8080/api)",
    )
    parser.add_argument(
        "--feature",
        default=None,
        help="Filter tests matching feature name (e.g. auth, feed, reels, stories)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output",
    )
    parser.add_argument(
        "-f", "--failfast",
        action="store_true",
        help="Stop on first failure",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Inspect and enumerate test suite without making network calls",
    )
    parser.add_argument(
        "--output-json",
        default=None,
        help="Path to write JSON test execution report",
    )

    args = parser.parse_args()

    # Set BASE_URL environment variable for test classes
    os.environ["BASE_URL"] = args.base_url.rstrip("/")

    suite = build_suite(args.tier, args.feature)
    total_tests = suite.countTestCases()

    print("=" * 72)
    print(" SocialApp Opaque-Box E2E Test Runner")
    print("=" * 72)
    print(f" Target API Base URL : {args.base_url}")
    print(f" Selected Tier       : {args.tier.upper()}")
    if args.feature:
        print(f" Feature Filter      : {args.feature}")
    print(f" Total Tests Loaded  : {total_tests}")
    print("=" * 72)

    if args.dry_run:
        print("\n[DRY RUN MODE] Enumerating tests in suite:")
        for idx, test in enumerate(suite, 1):
            print(f"  {idx:03d}. {test}")
        print(f"\nDry run complete. Verified {total_tests} test cases.")
        sys.exit(0)

    # Check backend connectivity
    is_up = check_backend_reachability(args.base_url)
    if not is_up:
        print(f"\n[WARNING] Backend at {args.base_url} is not responding.")
        print("          If backend is still starting or compiling in another milestone,")
        print("          start the Spring Boot server before executing live tests:")
        print("          cd backend && ./mvnw spring-boot:run -Dspring-boot.run.profiles=dev\n")

    start_wall = time.time()
    result = TestReportResult()
    result.failfast = args.failfast

    print("\nRunning test execution...\n")
    suite.run(result)
    elapsed_total = time.time() - start_wall

    # Print summary table
    print("\n" + "=" * 72)
    print(" Execution Summary")
    print("=" * 72)
    print(f" Tests Run  : {result.testsRun}")
    print(f" Passed     : {result.testsRun - len(result.failures) - len(result.errors) - len(result.skipped)}")
    print(f" Failed     : {len(result.failures)}")
    print(f" Errors     : {len(result.errors)}")
    print(f" Skipped    : {len(result.skipped)}")
    print(f" Duration   : {elapsed_total:.2f}s")
    print("=" * 72)

    if result.failures:
        print("\n--- Failures ---")
        for test, err in result.failures:
            print(f"\n[FAIL] {test}\n{err}")

    if result.errors:
        print("\n--- Errors ---")
        for test, err in result.errors:
            print(f"\n[ERROR] {test}\n{err}")

    if args.output_json:
        report = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "baseUrl": args.base_url,
            "tier": args.tier,
            "total": result.testsRun,
            "passed": result.testsRun - len(result.failures) - len(result.errors) - len(result.skipped),
            "failed": len(result.failures),
            "errors": len(result.errors),
            "skipped": len(result.skipped),
            "duration": elapsed_total,
            "records": result.test_records,
        }
        with open(args.output_json, "w") as f:
            json.dump(report, f, indent=2)
        print(f"\nJSON report written to: {args.output_json}")

    success = len(result.failures) == 0 and len(result.errors) == 0
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
