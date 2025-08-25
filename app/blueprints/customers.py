from flask import Blueprint, request, jsonify, current_app
from bson import ObjectId

customers_bp = Blueprint('customers', __name__)


@customers_bp.route('/', methods=['GET'])
def list_customers():
    """List customers. Query params may include tag filters etc."""
    # TODO: implement pagination + filtering
    docs = current_app.db.customers.find().limit(200)
    results = []
    for d in docs:
        d['_id'] = str(d['_id'])
        results.append(d)
    return jsonify(results)


@customers_bp.route('/', methods=['POST'])
def create_customer():
    """Create customer via JSON payload.

    Minimal validation here; keep heavy validation in a service layer or later.
    """
    payload = request.get_json()
    # TODO: validate fields (name, email...)
    res = current_app.db.customers.insert_one(payload)
    return jsonify({'inserted_id': str(res.inserted_id)}), 201


# Additional endpoints (GET /<id>, PUT, DELETE, import CSV) to add later