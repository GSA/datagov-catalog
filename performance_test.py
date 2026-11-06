#!/usr/bin/env python3
"""
Performance testing script for catalog application.
Measures actual load times for key pages and endpoints.
"""

import json
import statistics
import time
from datetime import datetime
from typing import Dict, List

import requests


class PerformanceTester:
    def __init__(self, base_url: str = "http://localhost:8080"):
        self.base_url = base_url
        self.session = requests.Session()
        self.results = []

    def measure_request(
        self, url: str, name: str, warmup: bool = True, iterations: int = 10
    ) -> Dict:
        """Measure response time for a URL."""
        full_url = f"{self.base_url}{url}"
        timings = []

        # Warmup request (don't count in stats)
        if warmup:
            try:
                self.session.get(full_url, timeout=30)
            except Exception as e:
                print(f"  ⚠️  Warmup failed for {name}: {e}")

        # Actual measurements
        errors = 0
        for i in range(iterations):
            try:
                start = time.time()
                response = self.session.get(full_url, timeout=30)
                elapsed = (time.time() - start) * 1000  # Convert to ms

                if response.status_code == 200:
                    timings.append(elapsed)
                else:
                    errors += 1
                    print(f"  ⚠️  Request {i+1} returned status {response.status_code}")
            except Exception as e:
                errors += 1
                print(f"  ⚠️  Request {i+1} failed: {e}")

        if not timings:
            return {
                "name": name,
                "url": url,
                "error": "All requests failed",
                "errors": errors,
            }

        result = {
            "name": name,
            "url": url,
            "iterations": len(timings),
            "errors": errors,
            "min_ms": round(min(timings), 2),
            "max_ms": round(max(timings), 2),
            "mean_ms": round(statistics.mean(timings), 2),
            "median_ms": round(statistics.median(timings), 2),
            "p95_ms": round(self._percentile(timings, 95), 2),
            "p99_ms": round(self._percentile(timings, 99), 2),
            "stdev_ms": round(statistics.stdev(timings), 2) if len(timings) > 1 else 0,
        }

        self.results.append(result)
        return result

    def _percentile(self, data: List[float], percentile: int) -> float:
        """Calculate percentile."""
        sorted_data = sorted(data)
        index = (percentile / 100) * len(sorted_data)
        if index.is_integer():
            return sorted_data[int(index) - 1]
        else:
            lower = sorted_data[int(index)]
            upper = sorted_data[min(int(index) + 1, len(sorted_data) - 1)]
            return (lower + upper) / 2

    def print_result(self, result: Dict):
        """Pretty print a single result."""
        if "error" in result:
            print(f"  ❌ {result['name']}: {result['error']}")
            return

        print(f"  ✓ {result['name']}")
        print(
            f"    Min: {result['min_ms']}ms | Mean: {result['mean_ms']}ms | "
            f"Median: {result['median_ms']}ms"
        )
        print(
            f"    P95: {result['p95_ms']}ms | P99: {result['p99_ms']}ms | "
            f"Max: {result['max_ms']}ms"
        )
        if result["errors"] > 0:
            print(
                f"    ⚠️  Errors: {result['errors']}/{result['iterations'] + result['errors']}"
            )

    def run_comprehensive_test(self):
        """Run comprehensive performance test suite."""
        print("=" * 80)
        print("CATALOG PERFORMANCE TEST")
        print(f"Base URL: {self.base_url}")
        print(f"Timestamp: {datetime.now().isoformat()}")
        print("=" * 80)
        print()

        # Test scenarios
        test_cases = [
            # Core pages
            ("/", "Homepage (no query)", True, 10),
            ("/search", "Search page (no query)", True, 10),
            ("/search?q=water", "Search: 'water'", True, 10),
            ("/search?q=health", "Search: 'health'", True, 10),
            ("/search?q=climate+change", "Search: 'climate change'", True, 10),
            ("/search?q=environment&page=2", "Search with pagination", True, 10),
            # Filters
            (
                "/search?q=&organization=test-org-1",
                "Search: filter by organization",
                True,
                10,
            ),
            (
                "/search?q=water&keywords=environment",
                "Search: query + keyword filter",
                True,
                10,
            ),
            # API endpoints
            ("/api/keywords?search=env&size=20", "API: Keyword autocomplete", True, 10),
            ("/api/organizations?size=20", "API: Organizations list", True, 10),
            ("/api/locations/search?search=wash", "API: Location search", True, 10),
            # Detail pages
            ("/datasets", "Datasets list page", True, 5),
            ("/organizations", "Organizations page", True, 5),
            # Static assets (should be fast)
            ("/static/css/styles.css", "Static: CSS file", False, 5),
            ("/static/img/data-gov-logo.svg", "Static: Logo", False, 5),
        ]

        print("📊 RUNNING TESTS...")
        print()

        for i, (url, name, warmup, iterations) in enumerate(test_cases, 1):
            print(f"[{i}/{len(test_cases)}] Testing: {name}")
            result = self.measure_request(url, name, warmup, iterations)
            self.print_result(result)
            print()
            time.sleep(0.5)  # Brief pause between tests

        self._print_summary()
        self._save_results()

    def _print_summary(self):
        """Print summary statistics."""
        print("=" * 80)
        print("SUMMARY")
        print("=" * 80)
        print()

        # Filter out failed tests
        successful = [r for r in self.results if "error" not in r]

        if not successful:
            print("❌ All tests failed!")
            return

        # Group by category
        pages = [
            r
            for r in successful
            if not r["url"].startswith("/api") and not r["url"].startswith("/static")
        ]
        apis = [r for r in successful if r["url"].startswith("/api")]
        static = [r for r in successful if r["url"].startswith("/static")]

        def print_category_stats(name: str, results: List[Dict]):
            if not results:
                return

            print(f"📈 {name}")
            print(
                f"   Fastest: {min(r['mean_ms'] for r in results):.2f}ms "
                f"({next(r['name'] for r in results if r['mean_ms'] == min(r['mean_ms'] for r in results))})"
            )
            print(
                f"   Slowest: {max(r['mean_ms'] for r in results):.2f}ms "
                f"({next(r['name'] for r in results if r['mean_ms'] == max(r['mean_ms'] for r in results))})"
            )
            print(f"   Average: {statistics.mean(r['mean_ms'] for r in results):.2f}ms")
            print(f"   P95:     {statistics.mean(r['p95_ms'] for r in results):.2f}ms")
            print()

        print_category_stats("PAGES", pages)
        print_category_stats("API ENDPOINTS", apis)
        print_category_stats("STATIC ASSETS", static)

        # Overall stats
        all_means = [r["mean_ms"] for r in successful]
        all_p95s = [r["p95_ms"] for r in successful]

        print("🎯 OVERALL")
        print(f"   Tests run: {len(self.results)}")
        print(f"   Successful: {len(successful)}")
        print(f"   Failed: {len(self.results) - len(successful)}")
        print(f"   Average response time: {statistics.mean(all_means):.2f}ms")
        print(f"   Average P95: {statistics.mean(all_p95s):.2f}ms")
        print()

        # Performance assessment
        print("📊 PERFORMANCE ASSESSMENT")
        avg_page_time = statistics.mean(r["mean_ms"] for r in pages) if pages else 0
        avg_api_time = statistics.mean(r["mean_ms"] for r in apis) if apis else 0

        def assess(time_ms: float, category: str) -> str:
            if category == "page":
                if time_ms < 500:
                    return "✅ EXCELLENT"
                elif time_ms < 1000:
                    return "✓ GOOD"
                elif time_ms < 2000:
                    return "⚠️  NEEDS IMPROVEMENT"
                else:
                    return "❌ POOR"
            else:  # API
                if time_ms < 200:
                    return "✅ EXCELLENT"
                elif time_ms < 500:
                    return "✓ GOOD"
                elif time_ms < 1000:
                    return "⚠️  NEEDS IMPROVEMENT"
                else:
                    return "❌ POOR"

        if pages:
            print(f"   Pages: {avg_page_time:.0f}ms {assess(avg_page_time, 'page')}")
        if apis:
            print(f"   APIs:  {avg_api_time:.0f}ms {assess(avg_api_time, 'api')}")
        print()

    def _save_results(self):
        """Save results to JSON file."""
        filename = (
            f"performance_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        with open(filename, "w") as f:
            json.dump(
                {
                    "timestamp": datetime.now().isoformat(),
                    "base_url": self.base_url,
                    "results": self.results,
                },
                f,
                indent=2,
            )
        print(f"💾 Results saved to: {filename}")
        print()

    def run_quick_test(self):
        """Run a quick test of key endpoints only."""
        print("=" * 80)
        print("CATALOG QUICK PERFORMANCE TEST")
        print(f"Base URL: {self.base_url}")
        print("=" * 80)
        print()

        quick_tests = [
            ("/", "Homepage", True, 5),
            ("/search?q=water", "Search", True, 5),
            ("/api/keywords?search=env", "API", True, 5),
        ]

        for url, name, warmup, iterations in quick_tests:
            result = self.measure_request(url, name, warmup, iterations)
            self.print_result(result)
            print()


def main():
    import sys

    base_url = "http://localhost:8080"
    quick_mode = False

    # Parse arguments
    for arg in sys.argv[1:]:
        if arg == "--quick":
            quick_mode = True
        elif arg.startswith("http"):
            base_url = arg

    tester = PerformanceTester(base_url)

    # Run appropriate test
    if quick_mode:
        tester.run_quick_test()
    else:
        tester.run_comprehensive_test()


if __name__ == "__main__":
    main()
