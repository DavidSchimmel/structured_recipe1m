import os
import spacy
import pickle

from data import loader
from structure_extraction import (graph_generator, recipe_parser)

GENERATE_RECIPE_CONTEXT_SIMPLE_GRAPH = False
GENERATE_RECIP_CONTEXT_WITH_SIMPLE_ACTIONS = False
GENERATE_RECIP_CONTEXT_WITH_INTERMEDIARY_ACTIONS = True


RECIPES_EXTENDED_PATH = os.path.abspath("./data/input/extended_recipes_with_quantities.json")
TRAIN_COMMENTS_PATH = os.path.abspath("./data/input/train_comments_subs.pkl")
TEST_COMMENTS_PATH = os.path.abspath("./data/input/test_comments_subs.pkl")
VAL_COMMENTS_PATH = os.path.abspath("./data/input/val_comments_subs.pkl")
MINIMAL_RECIPES_PATH = os.path.abspath("./data/input/minimal_recipe_dataset.pkl") # this one will be the one that we calculate with. It should look like a dict with recipe_id as key and value as dict with keys "ingredients" and "instructions" and the corresponding arrays
SIMPLE_RECIPE_INGREDIENT_GRAPH_DIR = os.path.abspath("./data/output/simple_recipe_ingredient_graph/")
SIMPLE_RECIPE_CONTEXT_SIMPLE_INSTRUCTIONS_DIR = os.path.abspath("./data/output/simple_recipe_with_context_simple_instructions/")
SIMPLE_RECIPE_CONTEXT_STRUCTURED_INSTRUCTIONS_DIR = os.path.abspath("./data/output/simple_recipe_with_context_structured_instructions/")

NODES_PATH = os.path.abspath("./data/input/nodes_191120.csv")
EDGES_PATH = os.path.abspath("./data/input/edges_191120.csv")

PARSED_RECIPES_PATH = os.path.abspath("./data/output")
REC_W_INGR_CNT_TO_STEP_PATH = os.path.abspath("./data/intermediary/recipes_with_ingr_cnt_to_step.pkl")
DISTINCT_VERBS_COUNT_PATH = os.path.abspath("./data/intermediary/distinct_verbs_cnt.pkl")
INGREDIENT_VARIANT_TO_NODE_IDX_PATH = os.path.abspath("./data/intermediary/ingredient_to_node_idx.pkl")

def main():
    recipes, flavourgraph_node_labels, flavourgraph_nodes = loader.load_data(
        MINIMAL_RECIPES_PATH,
        RECIPES_EXTENDED_PATH,
        TRAIN_COMMENTS_PATH,
        TEST_COMMENTS_PATH,
        VAL_COMMENTS_PATH,
        NODES_PATH
    )

    raw_nodes, raw_edges = loader.load_raw_graph(NODES_PATH, EDGES_PATH)

    node_to_tokens = recipe_parser.parseIngredients(recipes, flavourgraph_node_labels)
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


    if GENERATE_RECIPE_CONTEXT_SIMPLE_GRAPH:
        graph_generator.generateRecipeIngredientGraph(recipes, ingredient_variant_to_node_index, raw_nodes, raw_edges, SIMPLE_RECIPE_INGREDIENT_GRAPH_DIR)

    recipes_with_ingredients_to_steps = None
    if os.path.exists(REC_W_INGR_CNT_TO_STEP_PATH):
        with open(REC_W_INGR_CNT_TO_STEP_PATH, 'rb') as file:
            recipes_with_ingredients_to_steps = pickle.load(file)
    else:
        recipes_with_ingredients_to_steps = graph_generator.match_ingredients_to_instructions(recipes, parsed_recipes, node_to_tokens)
        with open(REC_W_INGR_CNT_TO_STEP_PATH, "wb") as rec_with_ingr_cnt_to_step_file:
            pickle.dump(recipes_with_ingredients_to_steps, rec_with_ingr_cnt_to_step_file)

    if GENERATE_RECIP_CONTEXT_WITH_SIMPLE_ACTIONS:
        graph_generator.generateRecipeInstructionsGraph(recipes, parsed_recipes, recipes_with_ingredients_to_steps, distinct_verbs, ingredient_variant_to_node_index, raw_nodes, raw_edges, SIMPLE_RECIPE_CONTEXT_SIMPLE_INSTRUCTIONS_DIR)

    if GENERATE_RECIP_CONTEXT_WITH_INTERMEDIARY_ACTIONS:
        graph_generator.generateStructuredRecipeInstructionsGraph(recipes, parsed_recipes, recipes_with_ingredients_to_steps, distinct_verbs, ingredient_variant_to_node_index, raw_nodes, raw_edges, SIMPLE_RECIPE_CONTEXT_STRUCTURED_INSTRUCTIONS_DIR)

    print("Done.")

if __name__ == "__main__":
    main()