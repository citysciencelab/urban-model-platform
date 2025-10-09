import re
from ump.core.interfaces.process_id_validator import ProcessIdValidatorPort

class ColonProcessId(ProcessIdValidatorPort):
    PATTERN = r"([^:]+):(.*)"

    def validate(self, process_id_with_prefix: str) -> bool:
        return bool(re.match(self.PATTERN, process_id_with_prefix))

    def extract(self, process_id_with_prefix: str) -> tuple[str, str]:
        match = re.match(self.PATTERN, process_id_with_prefix)
        if not match:
            raise ValueError(f"Process ID '{process_id_with_prefix}' does not match pattern 'provider:process_id'.")
        return match.group(1), match.group(2)

    def create(self, provider_prefix: str, process_id: str) -> str:
        return f"{provider_prefix}:{process_id}"
