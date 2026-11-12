
import json
import logging

from finpulse.processing.silver_pipeline import SilverPipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)


def main():
    pipeline = SilverPipeline()

    stats = pipeline.run()

    print("\n========== SILVER PIPELINE RESULTS ==========")
    print(json.dumps(stats, indent=4))
    print("=============================================")


if __name__ == "__main__":
    main()
