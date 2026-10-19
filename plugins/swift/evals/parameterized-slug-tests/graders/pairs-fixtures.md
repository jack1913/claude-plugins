---
# slugInputs[i] must be checked against slugOutputs[i]: zip, enumerated, or
# iterate either array's indices and subscript both.
type: regex
pattern: 'zip\(\s*slugInputs\s*,\s*slugOutputs|slug(?:Inputs|Outputs)\.(?:indices|enumerated)|0\s*\.\.<\s*slug(?:Inputs|Outputs)\.count'
target: { source: file, path: Tests/DemoTests/SlugTests.swift }
---
