import json
import os
import pickle
import csv

def load_recipes(minimal_ds_path, recipes_extended_path, train_set_path, test_set_path, val_set_path):

    recipes = None

    if os.path.isfile(minimal_ds_path):
        #just load and return that one
        with open(minimal_ds_path, "rb") as minimal_dataset_file:
            recipes = pickle.load(minimal_dataset_file)
        return recipes


    with open(recipes_extended_path, 'r') as recipe_extended_with_original_info:
        extended_recipes = json.load(recipe_extended_with_original_info)
    recipes_extended_dict = make_recipes_extended_dict(extended_recipes)

    recipes, unmatched_comments = createMinimalRecipeFromExtendedDictAndComments(
        recipes_extended_dict,
        train_set_path,
        test_set_path,
        val_set_path
    )

    print(f"Nr. of not matches comments: {len(unmatched_comments)}")
    with open(minimal_ds_path, "wb") as minimal_dataset_file:
        pickle.dump(recipes, minimal_dataset_file)

    return recipes

def getFlavourgraphIngrNodes(flavourgraph_nodes_path):
    graph_nodes = []
    with open(flavourgraph_nodes_path, 'r', newline='') as graph_nodes_file:
        csvreader = csv.reader(graph_nodes_file)
        _columns = next(csvreader)
        for row in csvreader:
            if row[3] == "ingredient":
                graph_nodes.append(row)
    return graph_nodes

def load_data(minimal_ds_path, recipes_extended_path, train_set_path, test_set_path, val_set_path, nodes_path):
    fg_nodes = getFlavourgraphIngrNodes(nodes_path)
    recipes = load_recipes(minimal_ds_path, recipes_extended_path, train_set_path, test_set_path, val_set_path)

    return recipes, fg_nodes

def load_raw_graph(nodes_path, edges_path):
    ingredient_count = 0
    raw_nodes = []
    with open(nodes_path, 'r', newline='') as graph_nodes_file:
        csvreader = csv.reader(graph_nodes_file)
        _columns = next(csvreader)
        for row in csvreader:
            raw_nodes.append(row)

    raw_edges = []
    with open(edges_path, 'r', newline='') as graph_edges_file:
        csvreader = csv.reader(graph_edges_file)
        _columns = next(csvreader)
        for row in csvreader:
            raw_edges.append(row)

    return raw_nodes, raw_edges

def make_recipes_extended_dict(extended_recipes):
    """Creates a dictionary with recipe id as key and all info in extended_recipes recipes as value. Additionally, aggregates all GT substitutions in recipe["subs"] if we encounter more than one GT sub per recipe_id in the extended recipes traversal. Copied from my statistical_ingredient_substitutions repo

    Args:
        extended_recipes (_type_): _description_

    Returns:
        dict[recipe_id, recipe]: with collected GT subs.
    """
    recipes_extended_dict = {}
    for recipe in extended_recipes:
        recipe_id = recipe["id"]
        if recipe_id not in list(recipes_extended_dict.keys()):
            recipes_extended_dict[recipe_id] = recipe
            recipes_extended_dict[recipe_id]["subs_collection"] = []
        if isinstance(recipe["subs"][0], list):
            for sub_list in recipe["subs"]:
                recipes_extended_dict[recipe_id]["subs_collection"].append(sub_list)
        else:
            recipes_extended_dict[recipe_id]["subs_collection"].append(recipe["subs"])

    return recipes_extended_dict

def createMinimalRecipeFromExtendedDictAndComments(recipes_extended_dict, train_set_path, test_set_path, val_set_path):
    minimal_recipe_ds = {}
    unmatched_comments = []

    with open(train_set_path, "rb") as train_comments_file:
        train_comments = pickle.load(train_comments_file)
    with open(test_set_path, "rb") as test_comments_file:
        test_comments = pickle.load(test_comments_file)
    with open(val_set_path, "rb") as val_comments_file:
        val_comments = pickle.load(val_comments_file)

    all_comments = train_comments + test_comments + val_comments

    for comment in all_comments:
        id = comment["id"]
        if id in recipes_extended_dict:
            recipe_extended = recipes_extended_dict[id]
            minimal_recipe = {
                "ingredients": recipe_extended["ingredients"],
                "instructions": recipe_extended["instructions"]
            }
            minimal_recipe_ds[recipe_extended["id"]] = minimal_recipe
        else:
            unmatched_comments.append(comment)
    return minimal_recipe_ds, unmatched_comments
