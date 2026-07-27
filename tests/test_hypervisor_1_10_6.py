#!/usr/bin/env python3
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BASE = os.path.join(ROOT, "netbox-discovery")
sys.path.insert(0, BASE)

from modules.hypervisor import engine_v4


def reclassify_row(existing_id=77):
    return {
        "object_type": "HOST",
        "asset_id": "HOST:vc1:SERIAL-001",
        "desired_name": "10.2.1.21",
        "serial": "SERIAL-001",
        "interfaces": [],
        "decision": "READY",
        "action": "RECLASSIFY_SAFE",
        "existing_id": existing_id,
        "target_tenant": "MIZU",
        "target_site": "FBA",
    }


def test_global_preflight_accepts_identical_reclassification_set():
    original_build = engine_v4.v3.build_plan
    try:
        live = {
            "records": [reclassify_row()],
            "ready_action_summary": {"RECLASSIFY_SAFE": 1},
        }
        engine_v4.v3.build_plan = lambda discovery, nb=None: (live, "/tmp/live-plan.json")
        result = engine_v4._global_preflight({}, live, object())
        assert result is live
    finally:
        engine_v4.v3.build_plan = original_build


def test_global_preflight_aborts_when_reclassification_identity_changes():
    original_build = engine_v4.v3.build_plan
    try:
        original = {"records": [reclassify_row(77)]}
        live = {
            "records": [reclassify_row(78)],
            "ready_action_summary": {"RECLASSIFY_SAFE": 1},
        }
        engine_v4.v3.build_plan = lambda discovery, nb=None: (live, "/tmp/live-plan.json")
        try:
            engine_v4._global_preflight({}, original, object())
            raise AssertionError("preflight deveria abortar quando existing_id muda")
        except RuntimeError as exc:
            assert "conjunto RECLASSIFY_SAFE mudou" in str(exc)
    finally:
        engine_v4.v3.build_plan = original_build


def test_global_preflight_aborts_on_review_before_any_write():
    original_build = engine_v4.v3.build_plan
    try:
        original = {"records": [reclassify_row()]}
        live = {
            "records": [
                reclassify_row(),
                {"asset_id": "VM:bad", "decision": "REVIEW", "action": "NOOP"},
            ],
            "ready_action_summary": {"RECLASSIFY_SAFE": 1},
        }
        engine_v4.v3.build_plan = lambda discovery, nb=None: (live, "/tmp/live-plan.json")
        try:
            engine_v4._global_preflight({}, original, object())
            raise AssertionError("preflight deveria abortar com REVIEW")
        except RuntimeError as exc:
            assert "REVIEW/BLOCKED" in str(exc)
            assert "nenhuma escrita iniciada" in str(exc)
    finally:
        engine_v4.v3.build_plan = original_build


def fake_query(nb, endpoint, **kwargs):
    if endpoint == "tenancy/tenants/":
        return [{"id": 4, "name": "MIZU"}]
    if endpoint == "dcim/sites/":
        return [{"id": 17, "name": "FBA"}]
    if endpoint == "dcim/devices/":
        return [{"id": 77, "name": "10.2.1.21", "serial": "SERIAL-001"}]
    if endpoint == "virtualization/virtual-machines/":
        return []
    if endpoint in ("ipam/ip-addresses/", "dcim/mac-addresses/", "virtualization/clusters/", "ipam/prefixes/"):
        return []
    return []


def test_reclassify_preflight_revalidates_strong_identity_immediately_before_write():
    original_query = engine_v4.base.query
    try:
        engine_v4.base.query = fake_query
        ctx = {"tenant": "MIZU", "site": "FBA"}
        subplan = {"records": [reclassify_row()]}
        assert engine_v4._reclassify_identity_preflight(ctx, subplan, object()) is True
    finally:
        engine_v4.base.query = original_query


def test_reclassify_preflight_rejects_changed_identity():
    original_query = engine_v4.base.query

    def changed_query(nb, endpoint, **kwargs):
        rows = fake_query(nb, endpoint, **kwargs)
        if endpoint == "dcim/devices/":
            return [{"id": 78, "name": "10.2.1.21", "serial": "SERIAL-001"}]
        return rows

    try:
        engine_v4.base.query = changed_query
        ctx = {"tenant": "MIZU", "site": "FBA"}
        subplan = {"records": [reclassify_row()]}
        try:
            engine_v4._reclassify_identity_preflight(ctx, subplan, object())
            raise AssertionError("preflight deveria rejeitar identity drift")
        except RuntimeError as exc:
            assert "identidade mudou" in str(exc)
    finally:
        engine_v4.base.query = original_query


def main():
    tests = [
        test_global_preflight_accepts_identical_reclassification_set,
        test_global_preflight_aborts_when_reclassification_identity_changes,
        test_global_preflight_aborts_on_review_before_any_write,
        test_reclassify_preflight_revalidates_strong_identity_immediately_before_write,
        test_reclassify_preflight_rejects_changed_identity,
    ]
    for test in tests:
        test()
        print("PASS", test.__name__)
    print("ALL 1.10.6 PREFLIGHT TESTS PASSED")


if __name__ == "__main__":
    main()
