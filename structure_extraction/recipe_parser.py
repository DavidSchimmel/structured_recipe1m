import pickle
import os
import time
from typing import List, Tuple, Dict, Set, Union, Any
from collections import defaultdict

import spacy
from spacy.tokens.doc import Doc
from spacy.symbols import *


STEP_DICTS_PATH = os.path.abspath("./data/intermediary/step_dicts.pkl")
NODE_TO_TOKENS_PATH = os.path.abspath("./data/intermediary/nodes_to_tokens.pkl")
NODE_TO_TOKENS_PATH = os.path.abspath("./data/intermediary/nodes_to_tokens.pkl")
NODE_TO_TOKENS_PATH = os.path.abspath("./data/intermediary/nodes_to_tokens.pkl")
NON_STOP_WORDS = {"all", "everything"}

def parseRecipes(recipes):
    instruction_list = spreadInstructions(recipes)

    # * load instruction tokens
    if os.path.isfile(STEP_DICTS_PATH):
        #just load and return that one
        with open(STEP_DICTS_PATH, "rb") as step_dicts_file:
            step_dicts = pickle.load(step_dicts_file)
    else:
        step_dicts = parseSteps(instruction_list)
        step_standard_dict = dict(step_dicts)

        with open(STEP_DICTS_PATH, "wb") as step_dicts_file:
            pickle.dump(step_standard_dict, step_dicts_file)

    return step_dicts

def parseIngredients(recipes, fg_node_labels):
    # * load node tokens
    if os.path.isfile(NODE_TO_TOKENS_PATH):
        #just load and return that one
        with open(NODE_TO_TOKENS_PATH, "rb") as nodes_to_tokens_file:
            node_to_tokens = pickle.load(nodes_to_tokens_file)
    else:
        node_to_tokens, recipes_to_node, node_to_ingrvars, problem_recipe_and_ingr = getIngredientTokens(recipes, fg_node_labels)
        with open(NODE_TO_TOKENS_PATH, "wb") as nodes_to_tokens_file:
            pickle.dump(node_to_tokens, nodes_to_tokens_file)

    return node_to_tokens

def getIngredientTokens(recipes, nodes):
    recipes_to_node = {}
    ingrvar_to_node = {}
    node_to_ingrvars = {}
    node_to_tokens = {}

    problem_recipe_and_ingr = []

    # * map all appearing ingredient variants to nodes and track nodes used in recipes
    for recipe_id, recipe in list(recipes.items()):
        recipe_nodes = []

        for ingr_vars in recipe["ingredients"]:
            # get the node label for the ingredient variants:
            node_label = None

            for ingr_var in ingr_vars:
                if ingr_var in nodes:
                    node_label = ingr_var
                    break

            if node_label is None:
                problem_recipe_and_ingr.append((recipe_id, ingr_vars))
                continue

            recipe_nodes.append(node_label)

            if node_label not in node_to_ingrvars:
                node_to_ingrvars[node_label] = []

            for ingr_var in ingr_vars:
                if ingr_var in node_to_ingrvars[node_label]:
                    continue

                node_to_ingrvars[node_label].append(ingr_var)
                ingrvar_to_node[ingr_var] = node_label

        recipes_to_node[recipe_id] = recipe_nodes

    ### * spread out the node to variants for use in the nlp pipeline
    node_and_variants_feed = []
    for node_label, ingredient_variants in node_to_ingrvars.items():
        for ingredient_variant in ingredient_variants:
            node_and_variants_feed.append((ingredient_variant.replace("_", " "), node_label))

    ### * run the pipeline
    nlp = spacy.load("en_core_web_trf")
    start_time = time.time()
    count = 0
    total_count = len(node_and_variants_feed)

    for doc, context in nlp.pipe(node_and_variants_feed, disable=["ner", "textcat", "token2vec"], as_tuples=True):
        if context not in node_to_tokens:
            node_to_tokens[context] = []

        node_to_tokens[context].append(clean_str(doc))

        count += 1
        if count % 1000 == 0:
            print(f"ingredient progress: {round(count/total_count, 4)} : {round(time.time()-start_time, 2)}s elapsed")


    return node_to_tokens, recipes_to_node, node_to_ingrvars, problem_recipe_and_ingr

def spreadInstructions(recipes):
    instruction_list = []

    for recipe_id, recipe in recipes.items():
        for instruction_nr, instruction in enumerate(recipe["instructions"]):
            step_tuple = (instruction, {"recipe_id": recipe_id, "step_nr": instruction_nr})
            instruction_list.append(step_tuple)
    return instruction_list

def parseSteps(instruction_list):
    """This function was adopted, with minor adjustments, from https://github.com/boschresearch/EaT-PIM/blob/main/eatpim/etl/parse_documents.py

    Args:
        instruction_list (_type_): _description_
    """
    nlp = spacy.load("en_core_web_trf")
    start_time = time.time()

    # dictionary of the form {recipe_id: {step_num: doc}}
    output_dict = defaultdict(lambda: {})

    count = 0
    total_count = len(instruction_list)

    for doc, context in nlp.pipe(instruction_list, disable=["ner", "textcat", "token2vec"], as_tuples=True):
        res = process_doc(doc)
        if (not res['subj_pred'] and
            not res['pred_obj'] and
            not res['modifying_subj_pred'] and
            not res['modifying_pred_obj']):
            # spaCy apparently has trouble parsing imperative sentences due to the lack of training data.
            # so when no verb is found in the sentence, we can try to modify it to make it easier to parse
            # e.g., "add water" can end up with a parse where "add water" is identified as a noun
            # instead, we add "you" to make the sentence be like "you add water"
            # this sometimes makes sentences look awkward grammatically, but it helps the parser
            # especially in cases where the first word is a verb
            modified_text = [('you '+res['step_string'], context)]
            newtry, context = list(nlp.pipe(modified_text, disable=["ner", "textcat", "token2vec"], as_tuples=True))[0]
            newres = process_doc(newtry)
            # if the updated parse changed enough that verbs were added, save the new result. otherwise,
            # we just keep the original.
            if len(newres['verbs']) > 0:
                # make the step's text be the same as the original, rather than the weird 'you ...' form
                newres['step_string'] = res['step_string']
                res = newres
        output_dict[context["recipe_id"]][context["step_nr"]] = res
        count += 1
        if count % 1000 == 0:
            print(f"recipe progress: {round(count/total_count, 4)} : {round(time.time()-start_time, 2)}s elapsed")

    return output_dict

def process_doc(doc):
    """This function was taken directly from https://github.com/boschresearch/EaT-PIM/blob/main/eatpim/etl/parse_documents.py

    Args:
        doc (_type_): _description_

    Returns:
        _type_: _description_
    """
    xcomp_connector = defaultdict(lambda: set())
    prep_connector_process = defaultdict(lambda: set())
    prep_connector_obj = defaultdict(lambda: set())

    verbs = set()
    verb_modifier = {}
    all_noun_chunks = set([chunk for chunk in doc.noun_chunks])
    nounchunk_deps = {}

    subj_pred = defaultdict(lambda: set())
    pred_obj = defaultdict(lambda: set())

    conj_tups = []
    process_spec_contents = set()

    for word in doc:
        if word.dep == punct:
            continue

        if word.pos == VERB and not word.is_stop:
            verbs.add(word)

        if word.dep == conj and word.pos in {VERB}:
            # save conjunctions and deal with them later
            # information might either all fall under the 'object' for a pred_obj
            # - e.g., ('slice', 'the onions and carrots'), where carrots/onions are connected by the conjunction
            # or it might be separated out if the conjunction is a verb
            # - e.g., ('chop', 'the carrots'), ('peel', 'the carrots'), ('dice', 'the carrots'), where
            # chop, peel, and dice are connected by the conjunction.
            # conjunctions for Nouns are handled differently, by checking for noun_chunks in a subtree
            conj_tups.append((word, word.head))
        elif word.dep in {prep}:
            # connect prepositions together at a later point if the PoS tag of the head is a verb.
            # e.g., this case occurs for "add to bowl" - "to" has a prep dependency to "add"
            if word.head.pos in {VERB, AUX}:
                prep_connector_process[word].add(word.head)
        elif word.dep in {prt}:
            # prt is a phrasal verb modifier - e.g., this case occurs for "mix in the butter", where
            # "mix in" should be considered a single action. "in" has the prt relation to "stir".
            # this differentiates between a case like "mix in a bowl", where "mix" is taking place in a bowl
            # rather than having the action "mix in" occur to a bowl.
            if word.head.pos in {VERB, AUX}:
                verb_modifier[word.head] = word
        elif word.dep == xcomp:
            # xcomp is an open clausal complement dependency.
            # this situation occurs in e.g., "use the knife to cut ...", where "cut" has the xcomp relation to
            # "use". we want to be able to make a connection from "knife" to "cut", so we store this information
            # in the xcomp_connector dict and make such connections later
            if word.pos in {VERB, AUX}:
                xcomp_connector[word].add(word.head)
        elif word.dep == advcl:
            # advcl is an adverbial clause modifier dependency.
            # this is a similar situation to the xcomp dep above - in a sentence like "using a knife, cut ...",
            # "using" has the advcl relation to "cut", and we once again want to make the connection between "knife"
            # and "cut" later on.
            if word.head.pos in {VERB, AUX}:
                xcomp_connector[word.head].add(word)
        elif word.head == word:
            # word is the root of the sentence, so it has no head relation for us to consider.
            continue
        elif word.pos in {AUX}:
            # auxiliary verbs, like Tense auxiliaries: has (done), is (doing), will (do).
            # ignoring these for now.
            continue
        elif word.head.pos in {VERB, AUX}:
            if word.dep in {mark, prep, prt} and word.head.head and word.head.head != word.head:
                process_spec_contents.add((word.head.head, word, word.head))
                continue
            if word.pos in {CONJ, CCONJ, ADV, ADP, PART}:
                # ignore certain PoS tags to ignore making direct pred-obj or sub-pref connections
                # for cases like "to cut", "and cut", and also throw away adverbs
                continue
            if word.dep in {dep}:
                # 'dep' is an unspecified dependency/unable to determine
                continue

            # use spacy's built-in nounchunks to get the whole part of the noun instead of a single word
            # e.g. get the noun chunk "ground meat" instead of just "meat"
            subtree = doc[word.left_edge.i:word.right_edge.i + 1]
            noun_chunks = [nc for nc in subtree.noun_chunks]
            if noun_chunks:
                for nc in noun_chunks:
                    # pass being in the dependency indicates it is a passive voice
                    if 'subj' in word.dep_ and 'pass' not in word.dep_:
                        subj_pred[nc].add(word.head)
                    else:
                        pred_obj[word.head].add(nc)
                    nounchunk_deps[nc] = nc[-1].dep_
            else:
                # no noun chunks, just assume it's one big noun or something that's not a noun
                if 'subj' in word.dep_ and 'pass' not in word.dep_:
                    subj_pred[subtree].add(word.head)
                else:
                    pred_obj[word.head].add(subtree)
                nounchunk_deps[subtree] = subtree[-1].dep_
        elif word.head.dep == advcl:
            if word.dep in {mark, prep} and word.head.head and word.head.head != word.head:
                process_spec_contents.add((word.head.head, word, word.head))
        elif word.head.dep in {prep}:
            # the head's dependency is a preposition
            # this indicates a situation like "brown the meat in a pot", where the current word we're looking at is
            # "pot", and its head is "in", which has the prep relation to "meat"
            # we want to be able to later make the connection ("brown", "in", "pot")
            subtree = doc[word.left_edge.i:word.right_edge.i + 1]
            noun_chunks = [nc for nc in subtree.noun_chunks]
            if len(noun_chunks):
                for nc in noun_chunks:
                    prep_connector_obj[word.head].add(nc)
                    nounchunk_deps[nc] = nc[-1].dep_
            else:
                prep_connector_obj[word.head].add(subtree)
                nounchunk_deps[subtree] = subtree[-1].dep_
        elif word.head.dep in {prt} and word.head.head:
            # this case occurs in cases like "cut in the butter with a fork ...", where we want to use the action
            # as "cut in". "in" has the prt relation to "cut", and "butter" is the pobj of "in".
            subtree = doc[word.left_edge.i:word.right_edge.i + 1]
            noun_chunks = [nc for nc in subtree.noun_chunks]
            if len(noun_chunks):
                for nc in noun_chunks:
                    if 'subj' in word.dep_ and 'pass' not in word.dep_:
                        subj_pred[nc].add(word.head.head)
                    else:
                        pred_obj[word.head.head].add(nc)
                    nounchunk_deps[nc] = nc[-1].dep_
            else:
                if 'subj' in word.dep_ and 'pass' not in word.dep_:
                    subj_pred[subtree].add(word.head.head)
                else:
                    pred_obj[word.head.head].add(subtree)
                nounchunk_deps[subtree] = subtree[-1].dep_

    changed = True
    # use a while loop so that we don't accidentally fail to add info from conjunctions due to unlucky ordering
    while changed:
        changed = False
        for tup in conj_tups:
            word = tup[0]
            head = tup[1]
            if word in subj_pred.keys():
                old_len = len(subj_pred[head])
                subj_pred[head] = subj_pred[head].union(subj_pred[word])
                if len(subj_pred[head]) != old_len:
                    changed = True
            if head in subj_pred.keys():
                old_len = len(subj_pred[word])
                subj_pred[word] = subj_pred[word].union(subj_pred[head])
                if len(subj_pred[word]) != old_len:
                    changed = True

            if word in pred_obj.keys():
                old_len = len(pred_obj[head])
                pred_obj[head] = pred_obj[head].union(pred_obj[word])
                if len(pred_obj[head]) != old_len:
                    changed = True
            if head in pred_obj.keys():
                old_len = len(pred_obj[word])
                pred_obj[word] = pred_obj[word].union(pred_obj[head])
                if len(pred_obj[word]) != old_len:
                    changed = True

    for xcomp_verb, pred_set in xcomp_connector.items():
        for pred in pred_set:
            if pred in pred_obj.keys():
                for obj in pred_obj[pred]:
                    # passive subjects - don't follow through with the logic
                    if "pass" in obj[-1].dep_:
                        continue
                    subj_pred[obj].add(xcomp_verb)

                    # loop through conjunctions again to make sure all relevant conjunctions are added
                    # this probably will only loop once
                    # this logic can very likely be greatly simplified/moved elsewhere to avoid this kind of loop
                    while True:
                        xc_verbs = subj_pred[obj]
                        prev_len = len(subj_pred[obj])
                        for tup in conj_tups:
                            if tup[0] in xc_verbs:
                                subj_pred[obj].add(tup[1])
                            elif tup[1] in xc_verbs:
                                subj_pred[obj].add(tup[0])
                        if len(subj_pred[obj]) == prev_len:
                            break

    for prep_word, prep_processes in prep_connector_process.items():
        if prep_word in prep_connector_obj.keys():
            prep_objs = prep_connector_obj[prep_word]
            for obj in prep_objs:
                for process in prep_processes:
                    process_spec_contents.add((process, prep_word, obj))

    # convert everything into strings before outputting
    output_strings: Dict[str, Any] = {
        "subj_pred": set(),
        "pred_obj": set(),
        "modifying_subj_pred": set(),
        "modifying_pred_obj": set(),
        "verbs": set(),
        "root_verb": "",
        "noun_chunks": set(),
        "action_prep_obj": set(),
        "step_string": str(doc)
    }
    for v in verbs:
        if v.dep_ == 'ROOT':
            output_strings['root_verb'] = clean_str(v, verb_modifier=verb_modifier)

    # verbs are all single words.
    for k, val_set in subj_pred.items():
        for v in val_set:
            cleaned_subj = clean_str(k)
            cleaned_pred = clean_str(v, verb_modifier=verb_modifier)
            if not (cleaned_subj and cleaned_pred):
                continue
            if v.dep in {advcl}:
                output_strings["modifying_subj_pred"].add((cleaned_subj,
                                                           cleaned_pred,
                                                           v.i))
            else:
                output_strings["subj_pred"].add((cleaned_subj,
                                                 cleaned_pred,
                                                 v.i, nounchunk_deps[k]))
    for k, val_set in pred_obj.items():
        for v in val_set:
            cleaned_obj = clean_str(v)
            cleaned_pred = clean_str(k, verb_modifier=verb_modifier)
            if not (cleaned_obj and cleaned_pred):
                continue
            if k.dep in {advcl}:
                output_strings["modifying_pred_obj"].add((cleaned_pred,
                                                          cleaned_obj,
                                                          k.i))
            else:
                output_strings["pred_obj"].add((cleaned_pred,
                                                cleaned_obj,
                                                k.i, nounchunk_deps[v]))

    output_strings["verbs"] = set(clean_str(verb, verb_modifier=verb_modifier) for verb in verbs)-{''}
    output_strings["noun_chunks"] = set(clean_str(np) for np in all_noun_chunks)-{''}
    # many prepositions also are considered stopwords, but don't filter them out.
    for (s,p,o) in process_spec_contents:
        clean_s = clean_str(s, verb_modifier=verb_modifier)
        clean_p = clean_str(p)
        clean_o = clean_str(o)
        if clean_s and clean_p and clean_o:
            output_strings["action_prep_obj"].add((clean_s, clean_p, clean_o, s.i))

    return output_strings

# convert everything from Spacy tokens to strings, and also get rid of stopwords
def clean_str(input, verb_modifier=None):
    """This function was taken directly from https://github.com/boschresearch/EaT-PIM/blob/main/eatpim/etl/parse_documents.py

    Args:
        input (_type_): _description_
        verb_modifier (_type_, optional): _description_. Defaults to None.

    Returns:
        _type_: _description_
    """
    if isinstance(input, spacy.tokens.token.Token):
        if input.lemma_ in {'be', 'let', 'use'}:
            return ''
        cleaned_str = str(input.lemma_).replace("-", "").replace("{", "").replace("}", "")
        if verb_modifier and input in verb_modifier.keys():
            cleaned_str += " "+str(verb_modifier[input]).replace("-", "").replace("{", "").replace("}", "")
        return cleaned_str

    if input[0].lemma_ in {'be', 'let', 'use'}:
        return ''

    relevant_words = [w for w in input
                      if ((not w.is_stop or str(w) in NON_STOP_WORDS)
                          and not str(w) == "-" and
                          not w.pos in {punct, PUNCT})]
    if not relevant_words:
        return ''
    elif len(relevant_words) == 1:
        cleaned_str = str(relevant_words[0].lemma_).replace("-", "").replace("{", "").replace("}", "")
        return cleaned_str

    # get rid of stay dashes, which seem relatively common
    cleaned_words = " ".join([str(w).replace("-", "").replace("{", "").replace("}","") for w in relevant_words[:-1]])
    # lemmatize the last word
    cleaned_words += f" {str(relevant_words[-1].lemma_).replace('-', '')}"
    return cleaned_words

def extract_verbs(parsed_recipes):
    distinct_verb_counts = {}

    for reicpe_id, recipe in parsed_recipes.items():
        for step_cnt, step in recipe.items():
            for verb in step["verbs"]:
                if verb not in list(distinct_verb_counts.keys()):
                    distinct_verb_counts[verb] = 0
                distinct_verb_counts[verb] += 1

    return distinct_verb_counts


def main():
    # check if the nlp package runs successfully
    nlp = spacy.load("en_core_web_trf")

if __name__ == "__main__":
    main()