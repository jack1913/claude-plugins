---
type: regex
pattern: '(?:you picked|did you mean|do you mean|which (?:list|one)|assum|taking (?:1|that|it)|read (?:it|that|your)|i(?:''ll| will) take|to confirm|just to (?:check|confirm))'
flags: i
target: last_message
weight: 1
---
The reply restates its reading or asks which list the 1 belongs to.
