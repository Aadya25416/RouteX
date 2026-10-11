"""CLI diagnostic command to validate the persisted road graph topology and connectivity."""

import json
import logging
import sys
from backend.services.graph_validator import GraphValidator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("graph_validator_cli")


def main():
    logger.info("Initializing graph topology validation...")
    validator = GraphValidator()
    try:
        results = validator.validate()
        print("\n" + "=" * 50)
        print("NER-LINK GRAPH TOPOLOGY VALIDATION REPORT")
        print("=" * 50)
        print(json.dumps(results, indent=2))
        print("=" * 50 + "\n")

        if not results.get("valid"):
            logger.error("Graph validation failed.")
            sys.exit(1)
        else:
            logger.info("Graph validation passed.")
    except Exception as exc:
        logger.error(f"Error during validation: {exc}", exc_info=True)
        sys.exit(1)
    finally:
        validator.close()


if __name__ == "__main__":
    main()
