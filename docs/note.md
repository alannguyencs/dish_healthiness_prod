# Activate virtual environment
```
python -m venv ./venv/
source venv/bin/activate
```

## To export environment variables from a .env file
```
Linux: eval $(grep -v '^#' .env | xargs -d'\n' -n1 echo export)
Mac OS: eval $(grep -v '^#' .env | xargs -0 -L1 echo export)
```

## Pre-commit setup
```
pre-commit clean
git add .pre-commit-config.yaml
pre-commit install
pre-commit run --all-files
```

## Run Test Cases
```
python -m unittest discover tests -v
```

## Tmux
```
tmux new -s food_healthiness
cd /root/food_healthiness
source venv/bin/activate
eval $(grep -v '^#' .env | xargs -d'\n' -n1 echo export)
python run_uvicorn.py --reload --port 2506
python run_uvicorn.py --port 2506

tmux a -t food_healthiness
```
