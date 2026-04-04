local OperationPreview = require('../src/Shared/OperationPreview')
local Protocol = require('../src/Shared/Protocol')

return function()
    local validEnvelope = {
        operation_id = 'op-1',
        kind = 'apply_script_patch',
        target_path = 'ReplicatedStorage/MyModule',
        payload = {
            script_source = 'return 1',
        },
        preconditions = {
            expected_sha256 = 'abc123',
        },
    }

    assert(Protocol.isOperationEnvelope(validEnvelope))
    assert(Protocol.isDestructive('delete_instance') == true)
    assert(Protocol.riskForKind('delete_instance') == 'high')
    assert(Protocol.riskForKind('read_scripts') == 'low')

    local summary = OperationPreview.summarize({
        validEnvelope,
        {
            operation_id = 'op-2',
            kind = 'delete_instance',
            target_path = 'Workspace/OldPart',
            payload = {},
            preconditions = {},
        },
    }, Protocol)

    assert(summary.total == 2)
    assert(summary.medium == 1)
    assert(summary.high == 1)
    assert(summary.destructive == 1)
end
