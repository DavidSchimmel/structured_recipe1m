import csv
import os
import pickle

from fuzzywuzzy import process

def generate_graph():
    assert False


def match_ingredients_to_instructions(recipes, parsed_recipes, node_to_tokens):
    match_threshold = 75
    for recipe_id in recipes:
        recipe_ingredients_at_step = {}
        recipe_ingredient_count_at_step = {}

        recipe = recipes[recipe_id]
        ingredients = recipe["ingredients"]

        ingredients_map = {}
        ingredient_variant_labels = []
        for counter, ingredient_variants in enumerate(ingredients):
            for ingredient_variant in ingredient_variants:
                ingredients_map[ingredient_variant] = counter
                ingredient_variant_labels.append(ingredient_variant)

        instructions = parsed_recipes[recipe_id]
        nouns_to_steps = {}

        for step, tokens in list(instructions.items()):
            for noun in tokens["noun_chunks"]:
                # save last instances of nouns to step in case there are some unmatched ingredients left
                nouns_to_steps[noun] = step

                noun = noun.replace(" ", "_")
                closest_match = process.extractOne(noun, ingredient_variant_labels)

                # maybe filter according to threshold
                if closest_match and closest_match[1] > match_threshold:
                    ingredient_count = ingredients_map[closest_match[0]]
                    if ingredient_count not in recipe_ingredient_count_at_step:
                        recipe_ingredient_count_at_step[ingredient_count] = []
                    recipe_ingredient_count_at_step[ingredient_count].append(step)

        # find the closest match for any ingredient that was not already associated with any step
        unmatched_ingredient_counts = {}
        for counter, ingredient_variants in enumerate(ingredients):
            if counter not in list(recipe_ingredient_count_at_step.keys()):
                unmatched_ingredient_counts[counter] = ingredient_variants[0]

        for ingredient_count, ingredient_variant in list(unmatched_ingredient_counts.items()):
            nouns = list(nouns_to_steps.keys())
            closest_match = process.extractOne(ingredient_variant, nouns)
            if closest_match:
                step = nouns_to_steps[closest_match[0]]

                recipe_ingredient_count_at_step[ingredient_count] = [(step)]

        recipe["ingr_cnt_at_step"] = recipe_ingredient_count_at_step

    return recipes

def getIngredientVariantToNode(recipes, nodes):
    ingredient_variant_to_node_index = {}
    ingredient_variant_to_node_label = {}

    node_label_to_index = {row[1]: row[0] for row in nodes}
    node_index_to_label = {row[0]: row[1] for row in nodes}

    unmatched_ingredient_variants = []

    for recipe_id, recipe in list(recipes.items()):
        for ingredient_variants in recipe["ingredients"]:
            target_index = None
            for ingredient_variant in ingredient_variants:
                if ingredient_variant in list(ingredient_variant_to_node_index.keys()):
                    target_index = ingredient_variant_to_node_index[ingredient_variant]
                    break
                elif ingredient_variant in list(node_label_to_index.keys()):
                    target_index = node_label_to_index[ingredient_variant]

            if target_index is None:
                unmatched_ingredient_variants.append(ingredient_variants)
                continue

            for ingredient_variant in ingredient_variants:
                if ingredient_variant not in list(ingredient_variant_to_node_index.keys()):
                    ingredient_variant_to_node_index[ingredient_variant] = target_index
                    ingredient_variant_to_node_label[ingredient_variant] = node_index_to_label[target_index]

    return ingredient_variant_to_node_index, ingredient_variant_to_node_label, unmatched_ingredient_variants

def generateRecipeIngredientGraph(recipes, ingredient_variant_to_node_index, nodes, edges, output_dir):
    # remove all ingredient-ingredient edges
    edges = [row for row in edges if row[3] != "ingr-ingr"]

    # add recipe_ids to nodes with recipe type
    node_id = 0
    for node in nodes:
        if int(node[0]) > node_id:
            node_id = int(node[0])

    rec_cnt = 0
    for recipe_id, recipe in list(recipes.items()):
        node_id = node_id + 1
        rec_cnt = rec_cnt + 1
        if rec_cnt % 1000 == 0:
            print(rec_cnt / len(recipes))

        nodes.append([str(node_id), recipe_id, "", "recipe", "no_hub"])

        recipe_node_edge_targets = []

        for ingredient_variants in recipe["ingredients"]:
            ingredient_node_id = ingredient_variant_to_node_index[ingredient_variants[0]]
            recipe_node_edge_targets.append(ingredient_node_id)


        # add recipe-ingredient-edges
        for edge_target_id in recipe_node_edge_targets:
            edges.append([str(node_id), str(edge_target_id), "1", "rec-ingr"])


    # create the output dir if it does not exist
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # save nodes to new file in output dir
    new_nodes_path = os.path.join(output_dir, "nodes.csv")
    cols = ["node_id","name","id","node_type","is_hub"]
    with open(new_nodes_path, 'w', newline='') as new_nodes_file:
        writer = csv.writer(new_nodes_file)
        writer.writerow(cols)
        for row in nodes:
            writer.writerow(row)

    # save edges to new file in output dir
    new_edges_path = os.path.join(output_dir, "edges.csv")
    cols = ["id_1","id_2","score","edge_type"]
    with open(new_edges_path, 'w', newline='') as new_edges_file:
        writer = csv.writer(new_edges_file)
        writer.writerow(cols)
        for row in edges:
            writer.writerow(row)

def getUniqueActionNodeName(action, existing_node_names):
    if action in existing_node_names:
        action = f"{action}_action"
    action = action.replace(" ", "_")
    return action

def generateRecipeInstructionsGraph(recipes, parsed_recipes, recipes_with_ingredients_to_steps, distinct_verbs, ingredient_variant_to_node_index, nodes, edges, output_dir):
    # remove all ingredient-ingredient edges
    edges = [row for row in edges if row[3] != "ingr-ingr"]
    existing_node_names = [row[1] for row in nodes]

    # add recipe_ids to nodes with recipe type
    node_id = 0
    for node in nodes:
        if int(node[0]) > node_id:
            node_id = int(node[0])

    action_to_node = {}
    # add instruction verbs to nodes
    for verb in distinct_verbs:
        node_id = node_id + 1
        action = getUniqueActionNodeName(verb, existing_node_names)
        nodes.append([str(node_id), action, "", "action", "no_hub"])
        action_to_node[verb] = node_id

    ingredient_verb_edges = []
    rec_cnt = 0
    for recipe_id, recipe in list(recipes.items()):
        recipe_with_ingredients_to_steps = recipes_with_ingredients_to_steps[recipe_id]
        recipe_tokens = parsed_recipes[recipe_id]

        node_id = node_id + 1
        rec_cnt = rec_cnt + 1
        if rec_cnt % 1000 == 0:
            print(rec_cnt / len(recipes))

        nodes.append([str(node_id), recipe_id, "", "recipe", "no_hub"])

        recipe_node_edge_targets = []

        for ingredient_variants in recipe["ingredients"]:
            ingredient_node_id = ingredient_variant_to_node_index[ingredient_variants[0]]
            recipe_node_edge_targets.append(ingredient_node_id)

        # add recipe-ingredient-edges
        for edge_target_id in recipe_node_edge_targets:
            edges.append([str(node_id), str(edge_target_id), "1", "rec-ingr"])

        ###

        for step, tokens in recipe_tokens.items():
            verbs = tokens["verbs"]
            for verb in verbs:
                edges.append([str(node_id), str(action_to_node[verb]), "1.0", "rec-act"])

        # add edges ingredient-action if it does not exist yet
        for ingredient_cnt, steps in recipe_with_ingredients_to_steps["ingr_cnt_at_step"].items():
            ingredient_variant = recipe_with_ingredients_to_steps["ingredients"][ingredient_cnt][0]
            ingredient_node = ingredient_variant_to_node_index[ingredient_variant]
            for step in steps:
                for verb in recipe_tokens[step]["verbs"]:
                    action_node = action_to_node[verb]
                    if ((ingredient_node, action_node) not in ingredient_verb_edges):
                        edges.append([str(ingredient_node), str(action_node), "1.0", "ingr-act"])
                        ingredient_verb_edges.append((ingredient_node, action_node))

    # create the output dir if it does not exist
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # save nodes to new file in output dir
    new_nodes_path = os.path.join(output_dir, "nodes.csv")
    cols = ["node_id","name","id","node_type","is_hub"]
    with open(new_nodes_path, 'w', newline='') as new_nodes_file:
        writer = csv.writer(new_nodes_file)
        writer.writerow(cols)
        for row in nodes:
            writer.writerow(row)

    # save edges to new file in output dir
    new_edges_path = os.path.join(output_dir, "edges.csv")
    cols = ["id_1","id_2","score","edge_type"]
    with open(new_edges_path, 'w', newline='') as new_edges_file:
        writer = csv.writer(new_edges_file)
        writer.writerow(cols)
        for row in edges:
            writer.writerow(row)

def generateStructuredRecipeInstructionsGraph(recipes, parsed_recipes, recipes_with_ingredients_to_steps, distinct_verbs, ingredient_variant_to_node_index, nodes, edges, output_dir):
    # remove all ingredient-ingredient edges
    edges = [row for row in edges if row[3] != "ingr-ingr"]
    existing_node_names = [row[1] for row in nodes]

    n_potential_error_recipes = 0
    potentially_fixed_recipes = 0

    # add recipe_ids to nodes with recipe type
    node_id = 0
    for node in nodes:
        if int(node[0]) > node_id:
            node_id = int(node[0])

    action_to_node = {}
    # add instruction verbs to nodes
    for verb in distinct_verbs:
        node_id = node_id + 1
        action = getUniqueActionNodeName(verb, existing_node_names)
        nodes.append([str(node_id), action, "", "action", "no_hub"])
        action_to_node[verb] = node_id

    ingredient_verb_edges = []
    rec_cnt = 0
    for recipe_id, recipe in list(recipes.items()):
        recipe_with_ingredients_to_steps = recipes_with_ingredients_to_steps[recipe_id]
        recipe_tokens = parsed_recipes[recipe_id]

        node_id = node_id + 1
        recipe_node_id = node_id
        rec_cnt = rec_cnt + 1
        if rec_cnt % 1000 == 0:
            print(rec_cnt / len(recipes))
            print(f"total recipes processed: {rec_cnt}")
            print(f"n potential error recipes: {n_potential_error_recipes}")

        nodes.append([str(recipe_node_id), recipe_id, "", "recipe", "no_hub"])

        recipe_node_edge_ingr_targets = []

        # register recipe ingredients for adding edges
        for ingredient_variants in recipe["ingredients"]:
            ingredient_node_id = ingredient_variant_to_node_index[ingredient_variants[0]]
            recipe_node_edge_ingr_targets.append(ingredient_node_id)

        # add recipe-ingredient-edges
        for edge_target_id in recipe_node_edge_ingr_targets:
            edges.append([str(node_id), str(edge_target_id), "1", "rec-ingr"])

        ###

        # add intermediary step nodes
        step_nodes = {}
        for step, tokens in recipe_tokens.items():
            verbs = tokens["verbs"]
            step_nodes[step] = []
            for verb in verbs:
                # add new step node
                node_id = node_id + 1
                node_label = f"{recipe_id}_{step}_{verb}"
                nodes.append([str(node_id), node_label, "", "step", "no_hub"])
                step_nodes[step].append(node_id)

                # connect step node to action node
                action_node = action_to_node[verb]
                edges.append([str(node_id), str(action_node), "1", "step-act"])
            # add intra-step edged
            if len(step_nodes[step]) > 1:
                active_step_node = step_nodes[step][0]
                for step_node in step_nodes[step]:
                    edges.append([str(active_step_node), str(step_node), "1", "step-step"])
                    active_step_node = step_node



        ### simulate structure:
        all_steps = [i for i in range(len(recipe_with_ingredients_to_steps['instructions']))]
        open_steps = [i for i in range(len(recipe_with_ingredients_to_steps['instructions']))]
        active_steps = []
        intermediary_item_edges = []

        # get all nodes that are connected to ingredients
        for ingredient_cnt, steps in list(recipe_with_ingredients_to_steps['ingr_cnt_at_step'].items()):
            # add the last step as active node that is assigned for aggregation or sequence
            last_ingredient_step = steps[-1]
            if last_ingredient_step not in active_steps:
                active_steps.append(last_ingredient_step)
            if last_ingredient_step in open_steps:
                open_steps.remove(last_ingredient_step)

            # rmeove chains of steps that are connected via same ingredients from the open steps and add (the last link of the chain is already added as active node in the previous code)
            for ingr_step_idx, ingr_step in enumerate(steps):
                if ingr_step != last_ingredient_step:
                    edge = (steps[ingr_step_idx], steps[ingr_step_idx] + 1)
                    if edge not in intermediary_item_edges:
                        intermediary_item_edges.append(edge)
                    if steps[ingr_step_idx] in open_steps:
                        open_steps.remove(steps[ingr_step_idx])

            # add edge between ingredient and first step where that ingredient is associated
            first_ingredient_step = steps[0]
            if (len(step_nodes[first_ingredient_step]) > 0):
                first_step_node_id = step_nodes[first_ingredient_step][0]
                ingredient_variant = recipe["ingredients"][ingredient_cnt][0]
                ingredient_node_id = ingredient_variant_to_node_index[ingredient_variant]
                edges.append([str(ingredient_node_id), str(first_step_node_id), "1", "ingr-step"])
                # TODO could try to add for the following associated steps if the first one has no verb found

        #if there are no open steps, combine all active steps in the last product.
        if not open_steps:
            if len(active_steps) < 2:
                print(f"potential error recipe: {recipe_id}")
                n_potential_error_recipes += 1
            else:
                active_steps.sort()
                for idx, active_step in enumerate(active_steps[:-1]):
                    edge = (active_steps[idx], active_steps[idx + 1])
                    if edge not in intermediary_item_edges:
                        intermediary_item_edges.append(edge)
            # last_active_step = active_steps[-1]
            # other_active_steps = active_steps[:-1]
            # for other_active_step in other_active_steps:
            #     edge = (other_active_step, last_active_step)
            #     if edge not in intermediary_item_edges:
            #         intermediary_item_edges.append(edge)
        else:
            #otherwise assign open steps to their previous step...
            if len(active_steps) < 2:
                print(f"potential error recipe: {recipe_id}")
                n_potential_error_recipes += 1
            # for step in open_steps:
            #     previous_step = step - 1
            #     edge = (previous_step, step)
            #     if edge not in intermediary_item_edges:
            #         intermediary_item_edges.append(edge)
            #     if previous_step in active_steps and previous_step != max(active_steps): # don't push the last active node back, though ()
            #         active_steps.append(step)
            #         active_steps.remove(previous_step)

            # ... and aggregate active steps
            else:
                current_active_step = active_steps[0]
                if len(active_steps) > 1:
                    for step in all_steps:
                        # if the step is still open, connect it to the previous step, move active step forward if necessary
                        if step in open_steps:
                            if step < 1:
                                continue
                            previous_step = step - 1
                            edge = (previous_step, step)
                            if edge not in intermediary_item_edges:
                                intermediary_item_edges.append(edge)
                            if previous_step in active_steps and previous_step != max(active_steps): # don't push the last active node back, though ()
                                active_steps.append(step)
                                active_steps.remove(previous_step)
                            if previous_step == current_active_step:
                                current_active_step = step

                        elif step in active_steps and step != current_active_step:
                            edge = (current_active_step, step)
                            if edge not in intermediary_item_edges:
                                intermediary_item_edges.append(edge)
                            current_active_step = step

        # connect intermediary product nodes according to step connections
        # TODO add some check to verify that the whole recipe is connected (but be careful not to add too many edges)
        # filled_steps = [step for step, nodes in step_nodes.items() if len(nodes) > 0]
        # for i, step in enumerate(filled_steps):
        #     if i+1 > len(filled_steps):
        #         break
        #     search_edge = (filled_steps[i], filled_steps[i+1])

        for intermediary_item_edge in intermediary_item_edges:
            source_step = intermediary_item_edge[0]
            target_step = intermediary_item_edge[1]
            if (len(step_nodes[source_step]) < 1) or (len(step_nodes[target_step]) < 1):
                continue
            source_node = step_nodes[source_step][-1]
            target_node = step_nodes[target_step][0]
            edges.append([str(source_node), str(target_node), "1", "step-step"])

        # connect recipe to last intermediary product
        filled_step_nodes = {step: nodes for step, nodes in step_nodes.items() if len(nodes) > 0}
        if len(filled_step_nodes) > 0:
            very_last_step_node = filled_step_nodes[list(filled_step_nodes.keys())[-1]][-1]
            edges.append([str(very_last_step_node), str(recipe_node_id), "1", "step-rec"])


        ### should only add the last step with an edge to the recipe
        # for step, tokens in recipe_tokens.items():
        #     verbs = tokens["verbs"]
        #     for verb in verbs:
        #         edges.append([str(node_id), str(action_to_node[verb]), "1.0", "rec-act"])

        # add edges ingredient-action if it does not exist yet (this can maybe stay the same, but need to replace the actions here with the abstract steps; connect steps to actions; connect ingredients with steps; connect steps between each other if they are connected, connect last step to recipe)
        # for ingredient_cnt, steps in recipe_with_ingredients_to_steps["ingr_cnt_at_step"].items():
        #     ingredient_variant = recipe_with_ingredients_to_steps["ingredients"][ingredient_cnt][0]
        #     ingredient_node = ingredient_variant_to_node_index[ingredient_variant]
        #     for step in steps:
        #         for verb in recipe_tokens[step]["verbs"]:
        #             action_node = action_to_node[verb]
        #             if ((ingredient_node, action_node) not in ingredient_verb_edges):
        #                 edges.append([str(ingredient_node), str(action_node), "1.0", "ingr-act"])
        #                 ingredient_verb_edges.append((ingredient_node, action_node))

    # create the output dir if it does not exist
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # save nodes to new file in output dir
    new_nodes_path = os.path.join(output_dir, "nodes.csv")
    cols = ["node_id","name","id","node_type","is_hub"]
    with open(new_nodes_path, 'w', newline='') as new_nodes_file:
        writer = csv.writer(new_nodes_file)
        writer.writerow(cols)
        for row in nodes:
            writer.writerow(row)

    # save edges to new file in output dir
    new_edges_path = os.path.join(output_dir, "edges.csv")
    cols = ["id_1","id_2","score","edge_type"]
    with open(new_edges_path, 'w', newline='') as new_edges_file:
        writer = csv.writer(new_edges_file)
        writer.writerow(cols)
        for row in edges:
            writer.writerow(row)



def generateStructuredRecipeInstructionsGraphReduced(recipes, parsed_recipes, recipes_with_ingredients_to_steps, distinct_verbs, ingredient_variant_to_node_index, nodes, edges, output_dir):
    # remove all ingredient-ingredient edges
    edges = [row for row in edges if row[3] != "ingr-ingr"]
    existing_node_names = [row[1] for row in nodes]

    n_potential_error_recipes = 0
    potentially_fixed_recipes = 0

    # add recipe_ids to nodes with recipe type
    node_id = 0
    for node in nodes:
        if int(node[0]) > node_id:
            node_id = int(node[0])

    action_to_node = {}
    # add instruction verbs to nodes
    for verb in distinct_verbs:
        node_id = node_id + 1
        action = getUniqueActionNodeName(verb, existing_node_names)
        nodes.append([str(node_id), action, "", "action", "no_hub"])
        action_to_node[verb] = node_id

    ingredient_verb_edges = []
    rec_cnt = 0
    for recipe_id, recipe in list(recipes.items()):
        recipe_with_ingredients_to_steps = recipes_with_ingredients_to_steps[recipe_id]
        recipe_tokens = parsed_recipes[recipe_id]

        node_id = node_id + 1
        recipe_node_id = node_id
        rec_cnt = rec_cnt + 1
        if rec_cnt % 1000 == 0:
            print(rec_cnt / len(recipes))
            print(f"total recipes processed: {rec_cnt}")
            print(f"n potential error recipes: {n_potential_error_recipes}")

        nodes.append([str(recipe_node_id), recipe_id, "", "recipe", "no_hub"])

        recipe_node_edge_ingr_targets = []

        # register recipe ingredients for adding edges
        for ingredient_variants in recipe["ingredients"]:
            ingredient_node_id = ingredient_variant_to_node_index[ingredient_variants[0]]
            recipe_node_edge_ingr_targets.append(ingredient_node_id)

        # add recipe-ingredient-edges
        for edge_target_id in recipe_node_edge_ingr_targets:
            edges.append([str(node_id), str(edge_target_id), "1", "rec-ingr"])

        ###

        # add intermediary step nodes
        step_nodes = {}
        for step, tokens in recipe_tokens.items():
            verbs = tokens["verbs"]
            step_nodes[step] = []
            for verb in verbs:
                # add new step node
                node_id = node_id + 1
                node_label = f"{recipe_id}_{step}_{verb}"
                nodes.append([str(node_id), node_label, "", "step", "no_hub"])
                step_nodes[step].append(node_id)

                # connect step node to action node
                action_node = action_to_node[verb]
                edges.append([str(node_id), str(action_node), "1", "step-act"])
            # add intra-step edged
            if len(step_nodes[step]) > 1:
                active_step_node = step_nodes[step][0]
                for step_node in step_nodes[step]:
                    edges.append([str(active_step_node), str(step_node), "1", "step-step"])
                    active_step_node = step_node



        ### simulate structure:
        all_steps = [i for i in range(len(recipe_with_ingredients_to_steps['instructions']))]
        open_steps = [i for i in range(len(recipe_with_ingredients_to_steps['instructions']))]
        active_steps = []
        intermediary_item_edges = []

        # get all nodes that are connected to ingredients
        for ingredient_cnt, steps in list(recipe_with_ingredients_to_steps['ingr_cnt_at_step'].items()):
            # add the last step as active node that is assigned for aggregation or sequence
            last_ingredient_step = steps[-1]
            if last_ingredient_step not in active_steps:
                active_steps.append(last_ingredient_step)
            if last_ingredient_step in open_steps:
                open_steps.remove(last_ingredient_step)

            # rmeove chains of steps that are connected via same ingredients from the open steps and add (the last link of the chain is already added as active node in the previous code)
            for ingr_step_idx, ingr_step in enumerate(steps):
                if ingr_step != last_ingredient_step:
                    edge = (steps[ingr_step_idx], steps[ingr_step_idx] + 1)
                    if edge not in intermediary_item_edges:
                        intermediary_item_edges.append(edge)
                    if steps[ingr_step_idx] in open_steps:
                        open_steps.remove(steps[ingr_step_idx])

            # add edge between ingredient and first step where that ingredient is associated
            first_ingredient_step = steps[0]
            if (len(step_nodes[first_ingredient_step]) > 0):
                first_step_node_id = step_nodes[first_ingredient_step][0]
                ingredient_variant = recipe["ingredients"][ingredient_cnt][0]
                ingredient_node_id = ingredient_variant_to_node_index[ingredient_variant]
                edges.append([str(ingredient_node_id), str(first_step_node_id), "1", "ingr-step"])
                # TODO could try to add for the following associated steps if the first one has no verb found

        #if there are no open steps, combine all active steps in the last product.
        if not open_steps:
            if len(active_steps) < 2:
                print(f"potential error recipe: {recipe_id}")
                n_potential_error_recipes += 1
            else:
                active_steps.sort()
                for idx, active_step in enumerate(active_steps[:-1]):
                    edge = (active_steps[idx], active_steps[idx + 1])
                    if edge not in intermediary_item_edges:
                        intermediary_item_edges.append(edge)
            # last_active_step = active_steps[-1]
            # other_active_steps = active_steps[:-1]
            # for other_active_step in other_active_steps:
            #     edge = (other_active_step, last_active_step)
            #     if edge not in intermediary_item_edges:
            #         intermediary_item_edges.append(edge)
        else:
            #otherwise assign open steps to their previous step...
            if len(active_steps) < 2:
                print(f"potential error recipe: {recipe_id}")
                n_potential_error_recipes += 1
            # for step in open_steps:
            #     previous_step = step - 1
            #     edge = (previous_step, step)
            #     if edge not in intermediary_item_edges:
            #         intermediary_item_edges.append(edge)
            #     if previous_step in active_steps and previous_step != max(active_steps): # don't push the last active node back, though ()
            #         active_steps.append(step)
            #         active_steps.remove(previous_step)

            # ... and aggregate active steps
            else:
                current_active_step = active_steps[0]
                if len(active_steps) > 1:
                    for step in all_steps:
                        # if the step is still open, connect it to the previous step, move active step forward if necessary
                        if step in open_steps:
                            if step < 1:
                                continue
                            previous_step = step - 1
                            edge = (previous_step, step)
                            if edge not in intermediary_item_edges:
                                intermediary_item_edges.append(edge)
                            if previous_step in active_steps and previous_step != max(active_steps): # don't push the last active node back, though ()
                                active_steps.append(step)
                                active_steps.remove(previous_step)
                            if previous_step == current_active_step:
                                current_active_step = step

                        elif step in active_steps and step != current_active_step:
                            edge = (current_active_step, step)
                            if edge not in intermediary_item_edges:
                                intermediary_item_edges.append(edge)
                            current_active_step = step

        # connect intermediary product nodes according to step connections
        # TODO add some check to verify that the whole recipe is connected (but be careful not to add too many edges)
        # filled_steps = [step for step, nodes in step_nodes.items() if len(nodes) > 0]
        # for i, step in enumerate(filled_steps):
        #     if i+1 > len(filled_steps):
        #         break
        #     search_edge = (filled_steps[i], filled_steps[i+1])

        for intermediary_item_edge in intermediary_item_edges:
            source_step = intermediary_item_edge[0]
            target_step = intermediary_item_edge[1]
            if (len(step_nodes[source_step]) < 1) or (len(step_nodes[target_step]) < 1):
                continue
            source_node = step_nodes[source_step][-1]
            target_node = step_nodes[target_step][0]
            edges.append([str(source_node), str(target_node), "1", "step-step"])

        # connect recipe to last intermediary product
        filled_step_nodes = {step: nodes for step, nodes in step_nodes.items() if len(nodes) > 0}
        if len(filled_step_nodes) > 0:
            very_last_step_node = filled_step_nodes[list(filled_step_nodes.keys())[-1]][-1]
            edges.append([str(very_last_step_node), str(recipe_node_id), "1", "step-rec"])


        ### should only add the last step with an edge to the recipe
        # for step, tokens in recipe_tokens.items():
        #     verbs = tokens["verbs"]
        #     for verb in verbs:
        #         edges.append([str(node_id), str(action_to_node[verb]), "1.0", "rec-act"])

        # add edges ingredient-action if it does not exist yet (this can maybe stay the same, but need to replace the actions here with the abstract steps; connect steps to actions; connect ingredients with steps; connect steps between each other if they are connected, connect last step to recipe)
        # for ingredient_cnt, steps in recipe_with_ingredients_to_steps["ingr_cnt_at_step"].items():
        #     ingredient_variant = recipe_with_ingredients_to_steps["ingredients"][ingredient_cnt][0]
        #     ingredient_node = ingredient_variant_to_node_index[ingredient_variant]
        #     for step in steps:
        #         for verb in recipe_tokens[step]["verbs"]:
        #             action_node = action_to_node[verb]
        #             if ((ingredient_node, action_node) not in ingredient_verb_edges):
        #                 edges.append([str(ingredient_node), str(action_node), "1.0", "ingr-act"])
        #                 ingredient_verb_edges.append((ingredient_node, action_node))

    # create the output dir if it does not exist
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # save nodes to new file in output dir
    new_nodes_path = os.path.join(output_dir, "nodes.csv")
    cols = ["node_id","name","id","node_type","is_hub"]
    with open(new_nodes_path, 'w', newline='') as new_nodes_file:
        writer = csv.writer(new_nodes_file)
        writer.writerow(cols)
        for row in nodes:
            writer.writerow(row)

    # save edges to new file in output dir
    new_edges_path = os.path.join(output_dir, "edges.csv")
    cols = ["id_1","id_2","score","edge_type"]
    with open(new_edges_path, 'w', newline='') as new_edges_file:
        writer = csv.writer(new_edges_file)
        writer.writerow(cols)
        for row in edges:
            writer.writerow(row)
