import os
import spacy
import pickle
import yaml

from data import loader
from structure_extraction import (graph_generator, recipe_parser)

config = yaml.safe_load(open(os.path.abspath("./config.yaml")))

RECIPES_EXTENDED_PATH = os.path.abspath("./data/input/extended_recipes_with_quantities.json")
TRAIN_COMMENTS_PATH = os.path.abspath("./data/input/train_comments_subs.pkl")
TEST_COMMENTS_PATH = os.path.abspath("./data/input/test_comments_subs.pkl")
VAL_COMMENTS_PATH = os.path.abspath("./data/input/val_comments_subs.pkl")
ARC_ONLY_SAMPLES_PATH = os.path.abspath("./data/input/tmp_total_arcelik_only_comments.pkl") # reduced recipe set that only contains recipes in the arc only dataset

MINIMAL_RECIPES_PATH = os.path.abspath("./data/input/minimal_recipe_dataset.pkl") # this one will be the one that we calculate with. It should look like a dict with recipe_id as key and value as dict with keys "ingredients" and "instructions" and the corresponding arrays

SIMPLE_RECIPE_INGREDIENT_GRAPH_DIR = os.path.abspath("./data/output/simple_recipe_ingredient_graph/")
SIMPLE_RECIPE_CONTEXT_SIMPLE_INSTRUCTIONS_DIR = os.path.abspath("./data/output/simple_recipe_with_context_simple_instructions/")
SIMPLE_RECIPE_CONTEXT_STRUCTURED_INSTRUCTIONS_DIR = os.path.abspath("./data/output/simple_recipe_with_context_structured_instructions/")
SIMPLE_RECIPE_CONTEXT_STRUCTURED_INSTRUCTIONS_ARC_DIR = os.path.abspath("./data/output/simple_recipe_with_context_structured_instructions_arc/")


NODES_PATH = os.path.abspath("./data/input/nodes_191120.csv")
EDGES_PATH = os.path.abspath("./data/input/edges_191120.csv")

PARSED_RECIPES_PATH = os.path.abspath("./data/output")
REC_W_INGR_CNT_TO_STEP_PATH = os.path.abspath("./data/intermediary/recipes_with_ingr_cnt_to_step.pkl")
DISTINCT_VERBS_COUNT_PATH = os.path.abspath("./data/intermediary/distinct_verbs_cnt.pkl")
INGREDIENT_VARIANT_TO_NODE_IDX_PATH = os.path.abspath("./data/intermediary/ingredient_to_node_idx.pkl")

def main():
    recipes, flavourgraph_nodes = loader.load_data(
        MINIMAL_RECIPES_PATH,
        RECIPES_EXTENDED_PATH,
        TRAIN_COMMENTS_PATH,
        TEST_COMMENTS_PATH,
        VAL_COMMENTS_PATH,
        NODES_PATH
    )

    raw_nodes, raw_edges = loader.load_raw_graph(NODES_PATH, EDGES_PATH)

    parsed_recipes = recipe_parser.parseRecipes(recipes)

    if os.path.exists(DISTINCT_VERBS_COUNT_PATH):
        with open(DISTINCT_VERBS_COUNT_PATH, 'rb') as file:
            distinct_verb_counts = pickle.load(file)
    else:
        distinct_verb_counts = recipe_parser.extract_verbs(parsed_recipes)
        with open(DISTINCT_VERBS_COUNT_PATH, 'wb') as file:
            pickle.dump(distinct_verb_counts, file)
    distinct_verbs = list(distinct_verb_counts.keys())


    if os.path.exists(INGREDIENT_VARIANT_TO_NODE_IDX_PATH):
        with open(INGREDIENT_VARIANT_TO_NODE_IDX_PATH, 'rb') as file:
            ingredient_variant_to_node_index = pickle.load(file)
    else:
        ingredient_variant_to_node_index, _ingredient_variant_to_node_label, _unmatched_ingredient_variants = graph_generator.getIngredientVariantToNode(recipes, flavourgraph_nodes)
        with open(INGREDIENT_VARIANT_TO_NODE_IDX_PATH, 'wb') as file:
            pickle.dump(ingredient_variant_to_node_index, file)


    if config["target_graph"]["bipartite_ingredients"]:
        graph_generator.generateRecipeIngredientGraph(recipes, ingredient_variant_to_node_index, raw_nodes, raw_edges, SIMPLE_RECIPE_INGREDIENT_GRAPH_DIR)

    recipes_with_ingredients_to_steps = None
    if os.path.exists(REC_W_INGR_CNT_TO_STEP_PATH):
        with open(REC_W_INGR_CNT_TO_STEP_PATH, 'rb') as file:
            recipes_with_ingredients_to_steps = pickle.load(file)
    else:
        recipes_with_ingredients_to_steps = graph_generator.match_ingredients_to_instructions(recipes, parsed_recipes)
        with open(REC_W_INGR_CNT_TO_STEP_PATH, "wb") as rec_with_ingr_cnt_to_step_file:
            pickle.dump(recipes_with_ingredients_to_steps, rec_with_ingr_cnt_to_step_file)

    if config['target_graphs']['bipartite_ingredients']:
        graph_generator.generateRecipeInstructionsGraph(recipes, parsed_recipes, recipes_with_ingredients_to_steps, distinct_verbs, ingredient_variant_to_node_index, raw_nodes, raw_edges, SIMPLE_RECIPE_CONTEXT_SIMPLE_INSTRUCTIONS_DIR)

    if config["target_graph"]["flow"]:
        graph_generator.generateStructuredRecipeInstructionsGraph(recipes, parsed_recipes, recipes_with_ingredients_to_steps, distinct_verbs, ingredient_variant_to_node_index, raw_nodes, raw_edges, SIMPLE_RECIPE_CONTEXT_STRUCTURED_INSTRUCTIONS_DIR)

    if config["target_graph"]["flow_reduced"] and SIMPLE_RECIPE_CONTEXT_STRUCTURED_INSTRUCTIONS_ARC_DIR:
        # because encoding all recipes with intermediary nodes leads to very many nodes, try if the model can be reasonably evaluated by encoding only the arc recipes (recipes that are contained in the arc_subs ground truth substitution data set)
        with open(ARC_ONLY_SAMPLES_PATH, "rb") as arc_only_file:
            arc_only_samples = pickle.load(arc_only_file)
        filter_list = list(set([sample["id"] for sample in arc_only_samples]))
        filtered_recipes = filter_recipes(recipes, filter_list)
        graph_generator.generateStructuredRecipeInstructionsGraph(filtered_recipes, parsed_recipes, recipes_with_ingredients_to_steps, distinct_verbs, ingredient_variant_to_node_index, raw_nodes, raw_edges, SIMPLE_RECIPE_CONTEXT_STRUCTURED_INSTRUCTIONS_ARC_DIR)

    print("Done.")

def filter_recipes(recipes, filter_list):
    filtered_recipes = {recipe_id: recipe for recipe_id, recipe in list(recipes.items()) if recipe_id in filter_list}
    return filtered_recipes

if __name__ == "__main__":
    main()