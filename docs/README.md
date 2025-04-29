# Banking Proposal Generator Documentation

This directory contains architecture and design documentation for the Banking Proposal Generator.

## Table of Contents

1. [Component Diagram](component-diagram.md) - Shows the logical components of the system and their relationships
2. [Sequence Diagram](sequence-diagram.md) - Illustrates the interaction between components during workflow execution
3. [System Architecture](system-architecture.md) - Provides a high-level view of the complete system with AWS infrastructure
4. [Data Flow Diagram](data-flow-diagram.md) - Visualizes how data moves through the system

## Key Architectural Decisions

### Serverless Architecture

The system uses AWS Lambda and Step Functions to provide a fully serverless architecture with the following benefits:

- Automatic scaling to handle variable loads
- Pay-per-use pricing model 
- Simplified deployment and operations
- Built-in resiliency and error handling

### Retrieval-Augmented Generation (RAG)

RAG is used to enhance the quality of generated proposals by providing relevant context:

- Document templates and clause libraries are indexed in a vector database
- Client requirements are used to retrieve the most relevant materials
- The generation model combines retrieved context with financial data

### Fine-Tuned LLM

The system uses a fine-tuned GPT-4-Turbo model specifically trained on financial proposals:

- Trained on 2 years of historic advice letters
- Achieves ≥90% template-field accuracy
- Significant improvement over base models in financial domain knowledge

### Strict Schema Validation

All generated content is validated against Pydantic schemas to ensure:

- All required sections are present
- Financial calculations are consistent
- Risk disclaimers are appropriate for recommended products

## Design Patterns

- **Choreography pattern** - Step Functions orchestrates workflow without tight coupling
- **Circuit breaker pattern** - Automatic handling of failures with retry mechanisms
- **Fallback pattern** - Graceful degradation when optimal generation fails
- **Input validation pattern** - Early validation of all inputs before processing