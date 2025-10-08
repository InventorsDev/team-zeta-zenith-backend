#!/bin/bash

# Test Runner Script for AI-Powered Customer Support Analyzer
# Runs different test suites with coverage reporting

set -e

echo "=================================="
echo "Running Test Suite"
echo "=================================="
echo

# Colors for output
GREEN='\033[0.32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

# Check if pytest is installed
if ! command -v pytest &> /dev/null; then
    print_error "pytest is not installed. Installing dependencies..."
    pip install -r requirements.txt
fi

# Parse command line arguments
TEST_SUITE=${1:-all}

case $TEST_SUITE in
    unit)
        print_status "Running Unit Tests..."
        pytest -m unit -v
        ;;

    integration)
        print_status "Running Integration Tests..."
        pytest -m integration -v
        ;;

    e2e)
        print_status "Running E2E Tests..."
        pytest -m e2e -v
        ;;

    fast)
        print_status "Running Fast Tests (unit + not slow)..."
        pytest -m "unit and not slow" -v
        ;;

    slow)
        print_status "Running Slow Tests..."
        pytest -m slow -v
        ;;

    security)
        print_status "Running Security Tests..."
        pytest -m security -v
        ;;

    coverage)
        print_status "Running All Tests with Coverage..."
        pytest --cov=app --cov-report=html --cov-report=term-missing --cov-fail-under=90
        print_status "Coverage report generated in htmlcov/index.html"
        ;;

    parallel)
        print_status "Running Tests in Parallel..."
        pytest -n auto -v
        ;;

    all|*)
        print_status "Running All Tests..."
        pytest -v

        echo
        print_status "Generating Coverage Report..."
        pytest --cov=app --cov-report=html --cov-report=term-missing

        echo
        print_status "Test Summary:"
        pytest --collect-only | grep "test session starts"
        ;;
esac

EXIT_CODE=$?

echo
echo "=================================="
if [ $EXIT_CODE -eq 0 ]; then
    print_status "All tests passed!"
else
    print_error "Some tests failed. Exit code: $EXIT_CODE"
fi
echo "=================================="

exit $EXIT_CODE
