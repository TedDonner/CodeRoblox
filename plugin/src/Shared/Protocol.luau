local Protocol = {}

local supportedKinds = {
    get_project_snapshot = true,
    get_selection = true,
    read_scripts = true,
    apply_script_patch = true,
    create_instance = true,
    update_properties = true,
    reparent_instance = true,
    delete_instance = true,
    run_playtest = true,
    collect_output = true,
    create_checkpoint = true,
    rollback_checkpoint = true,
}

local destructiveKinds = {
    delete_instance = true,
    rollback_checkpoint = true,
}

local riskByKind = {
    delete_instance = 'high',
    rollback_checkpoint = 'high',
    apply_script_patch = 'medium',
    create_instance = 'medium',
    update_properties = 'medium',
    reparent_instance = 'medium',
    run_playtest = 'medium',
}

function Protocol.isSupportedKind(kind)
    return supportedKinds[kind] == true
end

function Protocol.isDestructive(kind)
    return destructiveKinds[kind] == true
end

function Protocol.riskForKind(kind)
    return riskByKind[kind] or 'low'
end

function Protocol.isOperationEnvelope(value)
    if type(value) ~= 'table' then
        return false
    end

    if type(value.operation_id) ~= 'string' then
        return false
    end

    if type(value.kind) ~= 'string' or not Protocol.isSupportedKind(value.kind) then
        return false
    end

    if type(value.target_path) ~= 'string' then
        return false
    end

    local payloadType = type(value.payload)
    local preconditionsType = type(value.preconditions)
    return payloadType == 'table' and preconditionsType == 'table'
end

return Protocol
