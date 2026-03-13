from pathlib import Path
import argparse
import mlflow
import yaml


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/exp1.yaml")
    args = parser.parse_args()

    cfg = yaml.safe_load(Path(args.config).read_text())
    root = Path.cwd()
    artifacts = root / "artifacts" / "checkpoints"
    artifacts.mkdir(parents=True, exist_ok=True)

    mlflow.set_tracking_uri("http://127.0.0.1:1111")
    mlflow.set_experiment("backstage-server-lab")

    with mlflow.start_run():
        mlflow.log_params(cfg)
        for step in range(100):
            loss = 1.0 / (step + 1)
            mlflow.log_metric("loss", loss, step=step)
        ckpt = artifacts / "stub-model.ckpt"
        ckpt.write_text("placeholder checkpoint")
        mlflow.log_artifact(str(ckpt))
        print("stub_run_complete")


if __name__ == "__main__":
    main()
