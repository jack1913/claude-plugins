---
# slugInputs[i] must be checked against slugOutputs[i]: zip, or iterate the
# indices and subscript both arrays.
type: regex
pattern: 'zip\(\s*slugInputs\s*,\s*slugOutputs|slugInputs\.indices|0\s*\.\.<\s*slugInputs\.count'
target: { source: file, path: Tests/DemoTests/SlugTests.swift }
---
