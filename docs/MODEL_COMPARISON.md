# Model Comparison for Code Search Function-Calling (2025)

This document compares models suitable for generating schema-true tool calls for ast-grep and ripgrep.

## Executive Summary

- Primary (2×L40S): Qwen2.5-Coder-32B-Instruct
- Long context alternative: GLM-4-9B-Chat
- Maximum quality (quantized): Llama-3.1-70B-Instruct-AWQ

## Qwen2.5-Coder-32B-Instruct

Strengths:
- Strong function-calling performance
- Fits 2×L40S with tensor_parallel_size=2
- Good vLLM integration (hermes parser)

Limitations:
- 32K context

vLLM config example:
```python
from vllm import LLM
llm = LLM(model="Qwen/Qwen2.5-Coder-32B-Instruct", tensor_parallel_size=2, gpu_memory_utilization=0.9)
```

## GLM-4-9B-Chat

Strengths:
- Native function-calling, 131K context
- Fits single L40S

Limitations:
- Smaller model may reduce quality vs 32B

## Llama-3.1-70B-Instruct-AWQ (Quantized)

Strengths:
- High function-calling quality
- 131K context

Limitations:
- Requires INT4 quantization, slower

## Approximate Performance and Throughput

- Qwen2.5-Coder-32B: good balance of quality/speed
- GLM-4-9B: very high throughput, long context
- Llama-3.1-70B-AWQ: highest quality, slower

## Decision Guide

- Use Qwen2.5-Coder-32B for balanced dataset generation
- Use GLM-4-9B when long context is critical
- Use Llama-3.1-70B-AWQ for final high-quality passes

*Last Updated: October 2025*
