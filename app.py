from flask import Flask, abort, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy import desc

import json
import sys


DICT_KEYS = {'title', 'description', 'directions', 'ingredients'}

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///recipes.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

app.cur_recipe_id = 1
app.recipes = []

recipe_has_product = db.Table(
    'recipe_has_product',
    # db.Column('id', db.Integer, primary_key=True, autoincrement=True),
    db.Column('id_ingredient', db.Integer, db.ForeignKey('ingredient.id'), primary_key=True),
    db.Column('id_recipe', db.Integer, db.ForeignKey('recipe.id'), primary_key=True)
)


class Ingredient(db.Model):
    __tablename__ = 'ingredient'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    title = db.Column(db.String(80))
    measure = db.Column(db.String(10))
    amount = db.Column(db.Float)

    def __repr__(self):
        return '<ingredient %r>' % self.title


class Recipe(db.Model):
    __tablename__ = 'recipe'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    title = db.Column(db.String(80), nullable=False)
    description = db.Column(db.String(200), nullable=False)
    directions = db.Column(db.String(500), nullable=False)
    ingredients = db.relationship('Ingredient',
                                  secondary=recipe_has_product,
                                  lazy='subquery',
                                  backref=db.backref('recipes', lazy=True))

    def __repr__(self):
        return '<recipe %r>' % self.title

    def update(self, update_dictionary: dict):
        for col_name in self.__table__.columns.keys():
            if col_name in update_dictionary:
                setattr(self, col_name, update_dictionary[col_name])

        db.session.add(self)
        db.session.commit()

    # @hybrid_property
    # def directions(self):
    #     return str(self._directions).split('|')


@app.route('/api/recipe/new', methods=['POST'])
def add_recipe():
    request_json = request.get_json()

    try:
        recipe_dict = json.loads(request_json)
        if not recipe_dict \
                or recipe_dict.keys() != DICT_KEYS \
                or not recipe_dict['title'] \
                or not recipe_dict['description'] \
                or not recipe_dict['directions'] \
                or not recipe_dict['ingredients']:
            abort(400)

        recipe = Recipe(title=recipe_dict.get('title'),
                        description=recipe_dict.get('description'),
                        directions='|'.join(recipe_dict.get('directions')))
        for ingredient_obj in recipe_dict['ingredients']:
            ingredient = Ingredient(title=ingredient_obj.get('title'),
                                    measure=ingredient_obj.get('measure'),
                                    amount=ingredient_obj.get('amount'))
            recipe.ingredients.append(ingredient)

        db.session.add(recipe)
        db.session.flush()
        cur_recipe_id = recipe.id
        db.session.commit()

        return jsonify({"id": cur_recipe_id}), 200

    except ValueError:
        abort(400)


@app.route('/api/recipe/<int:recipe_id>', methods=['DELETE'])
def delete_recipe(recipe_id):
    recipe = Recipe.query.get(recipe_id)
    if recipe is None:
        abort(404)
    db.session.delete(recipe)
    db.session.commit()
    return '', 204


@app.route('/api/recipe/<int:recipe_id>', methods=['PUT'])
def update_recipe(recipe_id):
    recipe = Recipe.query.get(recipe_id)
    if not recipe:
        abort(404)

    request_json = request.get_json()

    try:
        recipe_dict = json.loads(request_json)
        if not recipe_dict \
                or recipe_dict.keys() != DICT_KEYS \
                or not recipe_dict['title'] \
                or not recipe_dict['description'] \
                or not recipe_dict['directions'] \
                or not recipe_dict['ingredients']:
            abort(400)

        recipe.update({'title': recipe_dict.get('title'),
                       'description': recipe_dict.get('description'),
                       'directions': '|'.join(recipe_dict.get('directions'))})
        ingredients = []
        for ingredient_obj in recipe_dict['ingredients']:
            ingredient = Ingredient(title=ingredient_obj.get('title'),
                                    measure=ingredient_obj.get('measure'),
                                    amount=ingredient_obj.get('amount'))
            ingredients.append(ingredient)
        recipe.ingredients = ingredients

        db.session.add(recipe)
        db.session.flush()
        db.session.commit()

        return '', 204

    except ValueError:
        abort(400)


@app.route('/api/recipe/<int:recipe_id>', methods=['GET'])
def get_recipe_by_id(recipe_id):
    recipe = Recipe.query.get(recipe_id)
    if not recipe:
        abort(404)
    recipe = recipe.__dict__
    del recipe['_sa_instance_state']
    del recipe['id']
    recipe['ingredients'] = [d.__dict__ for d in recipe['ingredients']]
    recipe['directions'] = recipe['directions'].split('|')
    for ingredient in recipe['ingredients']:
        del ingredient['_sa_instance_state']
    return jsonify(recipe)


@app.route('/api/recipe', methods=['GET'])
def search_by_ingredients():
    recipes = Recipe.query.order_by(desc(Recipe.title)).all()
    if not recipes:
        return jsonify(error="No recipe here yet")
    recipes = [d.__dict__ for d in recipes]
    for recipe in recipes:
        del recipe['_sa_instance_state']
        recipe['ingredients'] = [d.__dict__ for d in recipe['ingredients']]
        for ingredient in recipe['ingredients']:
            del ingredient['_sa_instance_state']

    ingredients = request.args.get('ingredients')
    max_directions = request.args.get('max_directions')
    if ingredients is None:
        abort(400)
    ingredients_list = ingredients.split('|')

    res_recipes = []
    for recipe in recipes:
        if set(ingredients_list) <= set([ingredient['title'] for ingredient in recipe['ingredients']]):
            recipe['directions'] = recipe['directions'].split('|')
            if max_directions and len(recipe['directions']) > int(max_directions):
                continue
            res_recipes.append(recipe)
    return jsonify(res_recipes)


if __name__ == '__main__':
    db.create_all()
    if len(sys.argv) > 1:
        arg_host, arg_port = sys.argv[1].split(':')
        app.run(host=arg_host, port=arg_port)
    else:
        app.run()
