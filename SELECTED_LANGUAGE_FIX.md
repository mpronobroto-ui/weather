# Selected Reply Language Fix

The UI-selected language is authoritative. LLM replies are explicitly instructed to ignore the input question language and are validated by Unicode script before being returned. If validation fails, the deterministic localized template is returned.
