"""Evaluate spaCy model and register to MLflow.

Evaluates trained model on test set and registers to MLflow model registry.
"""

from typing import Any

import mlflow
import mlflow.spacy
import structlog

logger = structlog.get_logger(__name__)


def evaluate_model(
    model_path: str,
    test_data_path: str,
) -> dict[str, Any]:
    """Evaluate spaCy model on test set.

    Args:
        model_path: Path to trained model
        test_data_path: Path to test data (.spacy)

    Returns:
        Evaluation metrics
    """
    import spacy
    from spacy.tokens import DocBin

    # Load model
    nlp = spacy.load(model_path)

    # Load test data
    db = DocBin()
    db.from_disk(test_data_path)
    docs = list(db.get_docs(nlp.vocab))

    # Evaluate
    scorer = nlp.evaluate(docs)

    metrics = {
        "ents_p": scorer["ents_p"],
        "ents_r": scorer["ents_r"],
        "ents_f": scorer["ents_f"],
        "ents_per_type": scorer.get("ents_per_type", {}),
    }

    logger.info("model_evaluation_completed", metrics=metrics)

    return metrics


def register_model_to_mlflow(
    model_path: str,
    model_name: str,
    metrics: dict[str, Any],
    version_tag: str,
) -> str:
    """Register model to MLflow model registry.

    Args:
        model_path: Path to trained model
        model_name: Name for model in registry
        metrics: Evaluation metrics
        version_tag: Version tag (e.g., "v1.0.0")

    Returns:
        Registered model version URI
    """
    # Set experiment
    mlflow.set_experiment("spacy_diplomatic_ner")

    with mlflow.start_run(run_name=f"register_{version_tag}"):
        # Log metrics
        mlflow.log_metrics(
            {
                "ents_p": metrics["ents_p"],
                "ents_r": metrics["ents_r"],
                "ents_f": metrics["ents_f"],
            }
        )

        # Log model
        mlflow.spacy.log_model(
            spacy_model=model_path,
            artifact_path="model",
            registered_model_name=model_name,
        )

        # Add version tag
        model_uri = f"models:/{model_name}/{version_tag}"
        client = mlflow.tracking.MlflowClient()
        try:
            client.set_model_version_tag(
                model_name, version_tag, "version", version_tag
            )
        except Exception as e:
            logger.warning("set_model_version_tag_failed", error=str(e))

        logger.info(
            "model_registered_to_mlflow",
            model_name=model_name,
            version_tag=version_tag,
            model_uri=model_uri,
        )

        return model_uri


def canary_deployment(
    model_name: str,
    version_tag: str,
    production_version_tag: str | None = None,
) -> None:
    """Deploy model as canary version.

    Args:
        model_name: Name of model in registry
        version_tag: Version tag for canary deployment
        production_version_tag: Current production version tag (optional)
    """
    client = mlflow.tracking.MlflowClient()

    # Get model version
    client.get_model_version(model_name, version_tag)

    # Transition to canary stage
    client.transition_model_version_stage(
        name=model_name,
        version=version_tag,
        stage="canary",
        archive_existing_versions=False,
    )

    logger.info(
        "canary_deployment_completed",
        model_name=model_name,
        version_tag=version_tag,
        stage="canary",
    )


if __name__ == "__main__":
    # Example usage
    model_path = "./models/model_final"
    test_data_path = "./data/test.spacy"
    model_name = "diplomatic_ner"
    version_tag = "v1.0.0"

    # Evaluate model
    metrics = evaluate_model(model_path, test_data_path)

    print("\nEvaluation Metrics:")
    print(f"Precision: {metrics['ents_p']:.4f}")
    print(f"Recall: {metrics['ents_r']:.4f}")
    print(f"F1 Score: {metrics['ents_f']:.4f}")

    # Register to MLflow
    model_uri = register_model_to_mlflow(model_path, model_name, metrics, version_tag)

    print(f"\nModel registered to MLflow: {model_uri}")

    # Deploy as canary
    canary_deployment(model_name, version_tag)

    print(f"\nCanary deployment completed for {model_name}:{version_tag}")
