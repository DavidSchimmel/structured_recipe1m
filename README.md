# Generate different graphs for Recipe1MSubs

This library creates several graphical representations for recipes in the recipe1MSubs dataset. To use this, you need to obtain the recipe1MSubs  dataset.

- code parts taken or adapted from https://github.com/boschresearch/EaT-PIM/blob/main/eatpim/etl can be found in the recipe parser and are marked in the function level comments

- `RECIPES_EXTENDED_PATH` can point to a file with the default recipe1MSubs recipe data, contained objects to only include `id`, `ingredients`, and `instructions`


Dependencies:
- spacy with `en_core_web_trf` model pretrained