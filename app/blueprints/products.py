from flask import Blueprint, request, jsonify, current_app

products_bp = Blueprint('products', __name__)


@products_bp.route('/', methods=['GET'])
def list_products():
    docs = current_app.db.products.find().limit(200)
    out = []
    for d in docs:
        d['_id'] = str(d['_id'])
        out.append(d)
    return jsonify(out)


@products_bp.route('/', methods=['POST'])
def create_product():
    payload = request.get_json()
    # Expect: title, description, optionally markers list
    # TODO: normalize markers (lowercase, dedupe)
    res = current_app.db.products.insert_one(payload)
    return jsonify({'inserted_id': str(res.inserted_id)}), 201


@products_bp.route('/<product_id>/match', methods=['POST'])
def match_product(product_id):
    """Trigger LLM pipeline: detect markers, match customers, return drafts.

    This endpoint should be thin: orchestrate calls to llm service + model helpers.
    """
    # TODO: call LLM service (see llm.py) and return result
    return jsonify({'status': 'not_implemented'}), 501
