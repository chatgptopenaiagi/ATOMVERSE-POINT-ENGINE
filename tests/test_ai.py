import pytest
from atomverse_point.ai import validate_proposal,propose
from atomverse_point.model import PointState

def test_readonly_ai_proposals_have_no_execution_privileges():
    assert validate_proposal({'action':'history_query','limit':5})=={'action':'history_query','limit':5}
    assert validate_proposal({'action':'explain','explanation':'Simulated amplitude is 1.','evidence_refs':['current_state']},{'current_state'})['action']=='explain'
    for proposal in ({'action':'history_query','sql':'DROP DATABASE x'},{'action':'history_query','limit':True},{'action':'explain','explanation':'x','evidence_refs':['invented-event']}):
        with pytest.raises(ValueError): validate_proposal(proposal,{'current_state'})

def test_ai_oscillator_commands_remain_bounded():
    c=validate_proposal({'action':'oscillator','enabled':True,'frequency':2,'phase':.5,'amplitude':3})
    assert c['frequency']==2
    with pytest.raises(ValueError): validate_proposal({'action':'oscillator','frequency':float('nan')})

def test_structured_output_grammar_rejects_cross_action_fields():
    import jsonschema
    from atomverse_point.ai import COMMAND_SCHEMA
    jsonschema.validate({'action':'appearance','radius':2},COMMAND_SCHEMA)
    jsonschema.validate({'action':'trajectory','trajectory':{'kind':'helix','duration':2}},COMMAND_SCHEMA)
    with pytest.raises(jsonschema.ValidationError): jsonschema.validate({'action':'appearance','radius':2,'frequency':1},COMMAND_SCHEMA)

@pytest.mark.parametrize('endpoint',['https://example.com','http://user:pass@localhost','http://127.0.0.1?forward=1','file:///etc/passwd'])
def test_ai_cannot_route_to_external_or_file_endpoints(endpoint):
    with pytest.raises(ValueError): propose('Move to origin',PointState().snapshot(),endpoint)
