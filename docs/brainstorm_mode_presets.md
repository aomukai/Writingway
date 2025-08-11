# Brainstorm Mode Preset Saving/Loading Functionality

## Overview
The preset system allows users to save, load, and manage configurations for repeated use in the Brainstorm Mode.

## Core Components

### 1. PresetManager
A component that handles preset operations.

#### Responsibilities:
- Save presets to disk
- Load presets from disk
- List available presets
- Delete presets
- Validate preset data

#### Key Methods:
- `save_preset()`: Save a preset with a name
- `load_preset()`: Load a preset by name
- `list_presets()`: List all available presets
- `delete_preset()`: Delete a preset by name
- `validate_preset()`: Validate preset data structure

### 2. Preset Data Structure
The data structure for storing preset configurations.

#### Attributes:
- `name`: Preset name
- `run_groups`: List of run group configurations
- `judge_config`: Judge model and prompt configuration
- `created_at`: Timestamp when preset was created
- `updated_at`: Timestamp when preset was last updated

#### RunGroup Structure:
- `provider`: Provider name
- `model`: Model name
- `runs`: Number of runs
- `temperature`: Temperature setting
- `delay`: Delay between requests
- `delay_unit`: Delay unit (seconds/minutes)
- `retries`: Number of retries
- `backoff_factor`: Exponential backoff factor

#### JudgeConfig Structure:
- `provider`: Judge provider name
- `model`: Judge model name
- `prompt_name`: Name of the judge prompt (if using saved prompt)
- `custom_prompt`: Custom judge prompt text (if using custom prompt)
- `temperature`: Judge temperature setting

### 3. Preset Storage
Presets will be stored as JSON files in the project directory.

#### File Location:
`Projects/{project_name}/brainstorm_presets/`

#### File Naming:
`{preset_name}.json`

## Implementation Details

### 1. Saving Presets
- Validate preset data before saving
- Serialize preset to JSON
- Save to project-specific presets directory
- Handle file naming conflicts
- Update preset metadata (created/updated timestamps)

### 2. Loading Presets
- List available presets from directory
- Load and parse JSON file
- Validate preset data structure
- Populate UI with preset values
- Handle missing or corrupted files

### 3. Preset Management
- List all presets in a combo box
- Allow users to delete presets
- Prevent deletion of built-in/system presets
- Handle preset name conflicts

### 4. Built-in Presets
Provide some default presets for common use cases:
- "Quick Comparison": 3 models, 1 run each, fast
- "Thorough Analysis": 5 models, 5 runs each, thorough
- "Budget Conscious": 2 models, 3 runs each, conservative settings

## Integration Points

- Integrated with the BrainstormModeDialog UI
- Uses project-specific storage paths
- Handles preset operations asynchronously to avoid blocking UI
- Provides feedback on save/load operations

## Error Handling

- Handle file I/O errors gracefully
- Validate preset data on load
- Provide meaningful error messages
- Recover from corrupted preset files
- Handle missing preset directories

## Performance Considerations

- Cache preset list to avoid repeated file system operations
- Load presets asynchronously
- Validate presets only when needed
- Handle large numbers of presets efficiently