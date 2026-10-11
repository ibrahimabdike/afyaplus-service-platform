import json
from logistics_mcp import check_stock, plan_delivery_route, get_delivery_eta, clinic_directory

def test_valid_stock():
    data = json.loads(check_stock("amoxicillin"))
    assert data["item"] == "amoxicillin"
    assert any(x["clinic"] == "Homa Bay Lakeside Clinic" and x["reorder_needed"]
               for x in data["stock"])

def test_invalid_item_is_data_not_exception():
    data = json.loads(check_stock("unobtainium"))
    assert "error" in data and "valid_items" in data

def test_invalid_route_is_data_not_exception():
    data = json.loads(plan_delivery_route("C99"))
    assert "error" in data and "valid_clinic_ids" in data

def test_route_visits_all_clinics():
    data = json.loads(plan_delivery_route("C01"))
    assert len(data["route"]) == 5
    assert data["route"][0]["id"] == "C01"

def test_eta_invalid_ids():
    assert "error" in json.loads(get_delivery_eta("C01", "C99"))

def test_directory_resource():
    data = json.loads(clinic_directory())
    assert len(data) == 5
