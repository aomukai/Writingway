# Brainstorm Mode Judge Evaluation System

## Overview
The judge evaluation system automatically evaluates and ranks the generated responses from the batch generation process using a configured judge model and prompt.

## Core Components

### 1. JudgeEvaluator
A component that handles the evaluation of generated responses.

#### Responsibilities:
- Format responses for evaluation
- Send evaluation requests to the judge model
- Parse and rank evaluation results
- Handle judge model errors

#### Key Methods:
- `evaluate_responses()`: Evaluate a list of responses using the judge model
- `format_evaluation_prompt()`: Format the prompt for the judge model
- `parse_judge_output()`: Parse the judge's output into rankings
- `rank_responses()`: Rank responses based on judge scores

### 2. Judge Configuration
Configuration for the judge model and prompt.

#### Attributes:
- `model`: Judge model configuration (provider, model name, etc.)
- `prompt`: Judge prompt configuration or custom prompt text
- `temperature`: Temperature setting for the judge model
- `max_tokens`: Maximum tokens for the judge response

### 3. EvaluationResult
A data structure to represent a ranked evaluation result.

#### Attributes:
- `rank`: Ranking position
- `score`: Numerical score from the judge (if available)
- `response`: The original generated response
- `explanation`: Judge's explanation for the ranking (if provided)

## Implementation Flow

1. **Preparation**
   - Collect all successful responses from batch generation
   - Format responses for evaluation (wrap in tags, add identifiers)

2. **Prompt Construction**
   - Load the selected judge prompt or use custom prompt
   - Insert the formatted responses into the judge prompt
   - Add any necessary instructions for ranking/scoring

3. **Evaluation Request**
   - Send the evaluation prompt to the judge model
   - Handle streaming or non-streaming responses
   - Apply appropriate timeout and error handling

4. **Result Parsing**
   - Parse the judge's output to extract rankings
   - Handle different output formats (numbered lists, scores, etc.)
   - Validate the parsed results

5. **Ranking**
   - Create EvaluationResult objects with rankings
   - Sort results by rank
   - Handle ties or missing rankings

6. **Presentation**
   - Format ranked results for display in the UI
   - Prepare results for insertion into the LLM output area

## Judge Prompt Format

The judge prompt should include instructions for evaluating and ranking the responses. A typical format might be:

```
You are an expert writing assistant tasked with evaluating and ranking multiple responses to a creative writing prompt.

The original prompt was:
{original_prompt}

The responses to evaluate are wrapped in <response> tags with identifiers:
{formatted_responses}

Please evaluate each response based on:
1. Relevance to the original prompt
2. Creativity and originality
3. Coherence and flow
4. Writing quality

Rank the responses from best to worst, providing a brief explanation for each ranking.

Format your response as a numbered list:
1. [Identifier] - [Brief explanation]
2. [Identifier] - [Brief explanation]
...
```

## Integration Points

- Receives responses from the batch generation system
- Uses the same LLM infrastructure as the main system
- Outputs ranked results to the LLM output preview area
- Handles errors and displays them appropriately

## Error Handling

- Handle judge model errors gracefully
- Provide fallback ranking if judge output is unparsable
- Allow users to rerun evaluation with different settings
- Log evaluation errors for debugging