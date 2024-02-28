# Generate different graphs for Recipe1MSubs

This library parses recipes from Recipe1MSubs and generates various graph representations from them.

## Prerequisits

### Inputs

- from Recipe1MSubs (follow the data preparation step [here](https://github.com/DavidSchimmel/gismo/blob/um_mt_extensions/gismo/README.md#data-preparation) if you need those files):
  - `train_comments_subs.pkl`
  - `test_comments_subs.pkl`
  - `val_comments_subs.pkl`
- from FlavorGraph:
  - `nodes_191120.csv` [source](https://github.com/lamypark/FlavorGraph/blob/master/input/nodes_191120.csv)
  - `edges_191120.csv` [source](https://github.com/lamypark/FlavorGraph/blob/master/input/edges_191120.csv)
- from ArcSubs:
  - `tmp_total_arcelik_only_comments.pkl`
    - this is needed if you want the reduced flow-graph like recipe representations that are filtered such that only recipes that are part of the given samples are represented.
    - this file must be a set of dictionaries, where each dictionary must contain an `"id"` key, where the values should be recipes from Recipe1MSubs
    - if the recipe IDs don't match, the filter will filter out all recipes and no graph will be represented.)
- other:
  - `extended_recipes_with_quantities.json`
    - this must be a list of recipes with keys containing at least:
    - `"id"` key pointing to the recipe if (should include the same recipe Ids as the samples used in the Recipe1MSubs samples)
    - `"ingredients"` key pointing to a list of lists, where each sublist contains ingredient variants.
    - `"instructions"` key pointing to a list of strings for the cooking instruction steps.

In the process, several intermediary files are created in the `intermediary` directory. They are used to quickly resume processing from those intermediary results and can be removed if no longer needed.

### Dependencies

- The conda environment can be loaded from the accompanying [environment.yml](./environment.yml)
- You may need to install spacy's `en-core-web-trf` separately

## Setup

- import the required files or set the paths in the main.py, set up the conda environment
- set up the config file, selecting the graphs you want to generate

## Usage

- simply run the `main()` function of the `main.py` file
- depending on the setttings in the config.yaml, different graphs will be generated

## Outputs

- depending on your configuration the scripts produce a `edges.csv` and a `nodes.csv` file in the following directories:
  - `data\output\simple_recipe_ingredient_graph` - for bipartite graph with recipe and ingredient nodes
  - `data\output\simple_recipe_with_context_simple_instructions` - for bipartite graph with recipe, action, and ingredient nodes
  - `data\output\simple_recipe_with_context_structured_instructions` - for a graph with intermediary node connected by directed edges
  - `data\output\simple_recipe_with_context_structured_instructions_arc` - for a graph with intermediary node connected by directed edges, but only for the ArcSubs recipes

## Credits

Code parts taken or adapted from https://github.com/boschresearch/EaT-PIM/blob/main/eatpim/etl can be found in the recipe parser and are marked in the function level comments