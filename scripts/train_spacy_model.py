"""Train spaCy model for diplomatic NER with hyperparameter search.

Generates config, performs hyperparameter search, and trains the model.
"""

import random
from pathlib import Path
from typing import Any

import mlflow
import structlog
from spacy.cli.train import train
from spacy.util import load_config

logger = structlog.get_logger(__name__)


def generate_config(
    base_config_path: str,
    output_path: str,
    hyperparameters: dict[str, Any],
) -> None:
    """Generate spaCy config with hyperparameters.

    Args:
        base_config_path: Path to base config file
        output_path: Path to output config file
        hyperparameters: Hyperparameters to override
    """
    config = load_config(base_config_path)

    # Override hyperparameters
    for key, value in hyperparameters.items():
        keys = key.split(".")
        current = config
        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]
        current[keys[-1]] = value

    # Save config
    import srsly

    srsly.write_yaml(output_path, config)
    logger.info(
        "config_generated", output_path=output_path, hyperparameters=hyperparameters
    )


def hyperparameter_search(
    train_data_path: str,
    dev_data_path: str,
    base_config_path: str,
    output_dir: str,
    n_trials: int = 10,
) -> dict[str, Any]:
    """Perform hyperparameter search for spaCy model.

    Search space:
    - dropout: [0.1, 0.2, 0.3, 0.4, 0.5]
    - learn_rate: [0.001, 0.002, 0.005]
    - n_epochs: [10, 20, 30]

    Args:
        train_data_path: Path to training data (.spacy)
        dev_data_path: Path to dev data (.spacy)
        base_config_path: Path to base config file
        output_dir: Output directory for models
        n_trials: Number of hyperparameter trials

    Returns:
        Best hyperparameters and metrics
    """
    # Define search space
    dropout_values = [0.1, 0.2, 0.3, 0.4, 0.5]
    learn_rate_values = [0.001, 0.002, 0.005]
    n_epochs_values = [10, 20, 30]

    best_score = 0.0
    best_hyperparameters = {}
    best_metrics = {}

    # Start MLflow run
    mlflow.set_experiment("spacy_diplomatic_ner")

    for trial in range(n_trials):
        # Sample hyperparameters
        hyperparameters = {
            "nlp.dropout": random.choice(dropout_values),
            "training.optimizer.learn_rate": random.choice(learn_rate_values),
            "training.max_epochs": random.choice(n_epochs_values),
        }

        logger.info(
            "hyperparameter_trial",
            trial=trial,
            hyperparameters=hyperparameters,
        )

        # Generate config
        config_path = Path(output_dir) / f"config_trial_{trial}.cfg"
        generate_config(base_config_path, str(config_path), hyperparameters)

        # Train model
        model_output_path = Path(output_dir) / f"model_trial_{trial}"

        try:
            with mlflow.start_run(run_name=f"trial_{trial}"):
                # Log hyperparameters
                mlflow.log_params(hyperparameters)

                # Train
                train(
                    str(config_path),
                    output_path=str(model_output_path),
                    overrides={
                        "paths.train": train_data_path,
                        "paths.dev": dev_data_path,
                    },
                )

                # Load metrics
                metrics_path = model_output_path / "meta.json"
                import srsly

                metrics = srsly.read_json(metrics_path)
                score = (
                    metrics.get("nlp", {})
                    .get("spacy", {})
                    .get("ner", {})
                    .get("ents_f", 0.0)
                )

                # Log metrics
                mlflow.log_metrics(
                    {
                        "ents_f": score,
                        "ents_p": metrics.get("nlp", {})
                        .get("spacy", {})
                        .get("ner", {})
                        .get("ents_p", 0.0),
                        "ents_r": metrics.get("nlp", {})
                        .get("spacy", {})
                        .get("ner", {})
                        .get("ents_r", 0.0),
                    }
                )

                logger.info("trial_completed", trial=trial, score=score)

                # Update best if improved
                if score > best_score:
                    best_score = score
                    best_hyperparameters = hyperparameters
                    best_metrics = metrics

        except Exception as e:
            logger.error("trial_failed", trial=trial, error=str(e))

    logger.info(
        "hyperparameter_search_completed",
        best_score=best_score,
        best_hyperparameters=best_hyperparameters,
    )

    return {
        "best_hyperparameters": best_hyperparameters,
        "best_score": best_score,
        "best_metrics": best_metrics,
    }


def train_final_model(
    train_data_path: str,
    dev_data_path: str,
    base_config_path: str,
    output_dir: str,
    best_hyperparameters: dict[str, Any],
) -> str:
    """Train final model with best hyperparameters.

    Args:
        train_data_path: Path to training data (.spacy)
        dev_data_path: Path to dev data (.spacy)
        base_config_path: Path to base config file
        output_dir: Output directory for final model
        best_hyperparameters: Best hyperparameters from search

    Returns:
        Path to trained model
    """
    # Generate final config
    config_path = Path(output_dir) / "config_final.cfg"
    generate_config(base_config_path, str(config_path), best_hyperparameters)

    # Train final model
    model_output_path = Path(output_dir) / "model_final"

    with mlflow.start_run(run_name="final_model"):
        mlflow.log_params(best_hyperparameters)

        train(
            str(config_path),
            output_path=str(model_output_path),
            overrides={
                "paths.train": train_data_path,
                "paths.dev": dev_data_path,
            },
        )

        # Load and log final metrics
        metrics_path = model_output_path / "meta.json"
        import srsly

        metrics = srsly.read_json(metrics_path)
        mlflow.log_metrics(
            {
                "ents_f": metrics.get("nlp", {})
                .get("spacy", {})
                .get("ner", {})
                .get("ents_f", 0.0),
                "ents_p": metrics.get("nlp", {})
                .get("spacy", {})
                .get("ner", {})
                .get("ents_p", 0.0),
                "ents_r": metrics.get("nlp", {})
                .get("spacy", {})
                .get("ner", {})
                .get("ents_r", 0.0),
            }
        )

        # Log model artifact
        mlflow.log_artifact(str(model_output_path), artifact_path="model")

    logger.info("final_model_trained", output_path=str(model_output_path))

    return str(model_output_path)


if __name__ == "__main__":
    # Example usage
    train_data_path = "./data/train.spacy"
    dev_data_path = "./data/dev.spacy"
    base_config_path = "./config/base_config.cfg"
    output_dir = "./models"

    # Create output directory
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # Perform hyperparameter search
    search_results = hyperparameter_search(
        train_data_path=train_data_path,
        dev_data_path=dev_data_path,
        base_config_path=base_config_path,
        output_dir=output_dir,
        n_trials=10,
    )

    # Train final model with best hyperparameters
    final_model_path = train_final_model(
        train_data_path=train_data_path,
        dev_data_path=dev_data_path,
        base_config_path=base_config_path,
        output_dir=output_dir,
        best_hyperparameters=search_results["best_hyperparameters"],
    )

    print(f"\nFinal model trained at: {final_model_path}")
    print(f"Best score: {search_results['best_score']}")
    print(f"Best hyperparameters: {search_results['best_hyperparameters']}")
