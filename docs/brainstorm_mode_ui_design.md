# Brainstorm Mode UI Design

## Overview
The Brainstorm Mode is a new feature that allows users to generate multiple LLM responses using different models and configurations, then automatically evaluate and rank them using a judge model.

## UI Components

### 1. Wizard Button
A new "Wizard" button will be added to the Action Beat view in the bottom stack, next to the existing preview, send, and stop buttons.

### 2. BrainstormModeDialog
A modal dialog that contains all the configuration options for the brainstorming process.

#### Layout
The dialog will have the following sections:

1. **Run Groups Configuration**
   - A table showing configured run groups with columns:
     - Model (combo box with available providers/models)
     - Runs (spin box for number of runs)
     - Temperature (double spin box)
     - Delay (spin box with seconds/minutes units)
   - Add/Remove buttons to manage run groups
   - Global retry settings with backoff options

2. **Judge Configuration**
   - Judge model selection (combo box with available providers/models)
   - Judge prompt selection (combo box with available prompts)
   - Custom judge prompt editor (text area)

3. **Preset Management**
   - Preset name input
   - Save preset button
   - Load preset combo box
   - Delete preset button

4. **Context Selection**
   - Option to include context from scenes and characters

5. **Progress and Control**
   - Progress bar showing overall progress
   - Detailed status text showing current operation
   - Cancel button to stop the process
   - Run button to start the brainstorming

#### Functionality
- Users can configure multiple run groups with different models, run counts, temperatures, and delays
- Users can select a judge model and prompt for evaluation
- Users can save and load presets for reuse
- Progress is tracked with a progress bar and detailed status updates
- Process can be cancelled at any time
- Results are displayed in a ranked list after completion

## Integration Points
- The dialog will be accessible from the Action Beat view via the new "Wizard" button
- Results will be displayed in the existing LLM output preview area
- Configuration will be saved to/loaded from project settings