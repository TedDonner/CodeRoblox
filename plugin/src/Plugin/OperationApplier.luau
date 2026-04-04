local ChangeHistoryService = game:GetService('ChangeHistoryService')

local InstancePath = require(script.Parent.InstancePath)

local OperationApplier = {}

local function createOutcome(operationId, success, message, changedPaths)
    return {
        operation_id = operationId,
        success = success,
        message = message,
        changed_paths = changedPaths or {},
    }
end

local function applyScriptPatch(operation)
    local target = InstancePath.findByPath(operation.target_path)
    if target == nil or not target:IsA('LuaSourceContainer') then
        return createOutcome(operation.operation_id, false, 'Script target not found.', {})
    end

    local ok, err = pcall(function()
        target.Source = operation.payload.script_source
    end)
    if not ok then
        return createOutcome(operation.operation_id, false, tostring(err), {})
    end

    return createOutcome(
        operation.operation_id,
        true,
        'Patched script source.',
        { operation.target_path }
    )
end

local function createInstance(operation)
    local parent = InstancePath.findByPath(operation.payload.parent_path)
    if parent == nil then
        return createOutcome(operation.operation_id, false, 'Parent path not found.', {})
    end

    local instance = Instance.new(operation.payload.class_name)
    instance.Name = operation.payload.name
    instance.Parent = parent

    local properties = operation.payload.properties or {}
    for propertyName, value in pairs(properties) do
        pcall(function()
            instance[propertyName] = value
        end)
    end

    return createOutcome(operation.operation_id, true, 'Created instance.', {
        InstancePath.getPath(instance),
    })
end

local function updateProperties(operation)
    local target = InstancePath.findByPath(operation.target_path)
    if target == nil then
        return createOutcome(operation.operation_id, false, 'Target not found.', {})
    end

    for propertyName, value in pairs(operation.payload.properties) do
        local ok, err = pcall(function()
            target[propertyName] = value
        end)
        if not ok then
            return createOutcome(operation.operation_id, false, tostring(err), {})
        end
    end

    return createOutcome(
        operation.operation_id,
        true,
        'Updated properties.',
        { operation.target_path }
    )
end

local function reparentInstance(operation)
    local target = InstancePath.findByPath(operation.target_path)
    local newParent = InstancePath.findByPath(operation.payload.new_parent_path)
    if target == nil or newParent == nil then
        return createOutcome(operation.operation_id, false, 'Target or new parent not found.', {})
    end

    target.Parent = newParent
    return createOutcome(operation.operation_id, true, 'Reparented instance.', {
        InstancePath.getPath(target),
    })
end

local function deleteInstance(operation)
    local target = InstancePath.findByPath(operation.target_path)
    if target == nil then
        return createOutcome(operation.operation_id, false, 'Target not found.', {})
    end

    target:Destroy()
    return createOutcome(
        operation.operation_id,
        true,
        'Deleted instance.',
        { operation.target_path }
    )
end

local function createCheckpoint(operation)
    local label = operation.payload.label or ('checkpoint-' .. operation.operation_id)
    ChangeHistoryService:SetWaypoint(label)
    return createOutcome(operation.operation_id, true, 'Checkpoint waypoint created.', {})
end

local function rollbackCheckpoint(operation)
    return createOutcome(
        operation.operation_id,
        false,
        string.format(
            'Rollback for checkpoint %s is not implemented yet.',
            tostring(operation.payload.checkpoint_id)
        ),
        {}
    )
end

local handlers = {
    apply_script_patch = applyScriptPatch,
    create_instance = createInstance,
    update_properties = updateProperties,
    reparent_instance = reparentInstance,
    delete_instance = deleteInstance,
    create_checkpoint = createCheckpoint,
    rollback_checkpoint = rollbackCheckpoint,
}

function OperationApplier.applyBatch(operations)
    local outcomes = {}

    for _, operation in ipairs(operations) do
        local handler = handlers[operation.kind]
        if handler == nil then
            table.insert(
                outcomes,
                createOutcome(
                    operation.operation_id,
                    false,
                    'Unsupported operation for plugin.',
                    {}
                )
            )
        else
            table.insert(outcomes, handler(operation))
        end
    end

    return outcomes
end

return OperationApplier
