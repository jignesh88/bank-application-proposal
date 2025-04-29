# Contributing to Banking Proposal Generator

Thank you for your interest in contributing to the Banking Proposal Generator! This document provides guidelines and instructions for contributing to this project.

## Code of Conduct

All contributors are expected to adhere to the project's code of conduct. Please be respectful and constructive in all interactions.

## Getting Started

1. Fork the repository on GitHub
2. Clone your fork locally
3. Set up the development environment following the instructions in the README

## Development Workflow

1. Create a new branch for your feature or bugfix: `git checkout -b feature/your-feature-name`
2. Make your changes
3. Run tests to ensure your changes don't break existing functionality: `python -m unittest discover tests`
4. Commit your changes with descriptive commit messages
5. Push your branch to your fork on GitHub
6. Submit a pull request to the main repository

## Coding Standards

- Follow PEP 8 style guidelines for Python code
- Use meaningful variable and function names
- Write docstrings for all functions, classes, and modules
- Add type hints where appropriate
- Include unit tests for new functionality

## Pull Request Process

1. Ensure your code passes all tests
2. Update documentation if necessary
3. Make sure your code is properly formatted
4. Pull requests should target the `main` branch

## AWS Infrastructure

When making changes to the AWS infrastructure:

1. Use CDK for all infrastructure changes
2. Test infrastructure changes locally with CDK synth
3. Document any new environment variables or configuration requirements

## Submitting Issues

When submitting issues, please provide:

- A clear and descriptive title
- A detailed description of the issue
- Steps to reproduce the issue
- Expected and actual behavior
- Environment details (OS, Python version, etc.)

## License

By contributing to this project, you agree that your contributions will be licensed under the same MIT License that covers the project.