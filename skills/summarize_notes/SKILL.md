---
name: summarize_notes
description: Summarize recent notes for a given project
version: 0.1.0
parameters:
  project:
    type: string
    description: Project name to look up notes for
    required: true
  k:
    type: integer
    description: Number of recent notes to include
    required: false
    default: 5
---

# summarize_notes

Read the {k} most recent notes for project {project} and produce a concise 3-bullet summary.
