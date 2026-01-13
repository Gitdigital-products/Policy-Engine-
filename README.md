<!-- Security Badges -->
![Security Foundational](https://img.shields.io/badge/security-foundational-blue)
![Security Scanning](https://img.shields.io/badge/security-scanning-active-green)

<!-- Activity Badges -->
![Last Commit](https://img.shields.io/badge/commit-current-brightgreen)
![Issues Health](https://img.shields.io/badge/issues-healthy-brightgreen)
![Release Cadence](https://img.shields.io/badge/releases-active-brightgreen)

<!-- Maturity Badges -->
![CI Status](https://img.shields.io/badge/CI-passing-brightgreen)
![Versioning](https://img.shields.io/badge/versioning-semver-blue)

<!-- Technology Badges -->
![Primary Language](https://img.shields.io/badge/language-JavaScript-yellow)
![Containerized](https://img.shields.io/badge/containerized-Docker-blue)

<!-- Quality Badges -->
![Linting](https://img.shields.io/badge/linting-passing-brightgreen)
![Documentation](https://img.shields.io/badge/docs-complete-brightgreen)

<!-- Community Badges -->
![Contributors](https://img.shields.io/badge/contributors-2-blue)
![License](https://img.shields.io/badge/license-MIT-yellow)


# GitDigital Policy Engine

A Rules-as-Code engine for eligibility, compliance logic, and thresholds evaluation.

## Features

- **Rules-as-Code**: Define policies as code with version control
- **Multiple Formats**: Support for JSON, YAML, and Python DSL
- **Threshold Management**: Built-in threshold checking and validation
- **Compliance Logic**: Evaluate compliance against rule sets
- **Eligibility Engine**: Determine eligibility based on multiple criteria
- **Extensible**: Custom operators and rule types
- **Caching**: Performance optimization with caching
- **API First**: REST API and CLI interfaces
- **Audit Trail**: Complete decision logging and traceability

## Installation

### Using pip

```bash
pip install gitdigital-policy-engine
```

From source

```bash
git clone https://github.com/gitdigital/policy-engine.git
cd policy-engine
pip install -e .
``

Using Docker

```bash
docker-compose up
```

Quick Start

1. Define a Policy

Create a policy file policy.yaml:

```yaml
id: student-loan-eligibility
name: Student Loan Eligibility
version: "1.0.0"
rule_sets:
  basic:
    id: basic
    name: Basic Eligibility
    rules:
      - id: age-requirement
        name: Age Requirement
        condition:
          operator: gte
          left_operand: $age
          right_operand: 18
```







