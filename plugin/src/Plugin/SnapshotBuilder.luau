local Selection = game:GetService('Selection')

local InstancePath = require(script.Parent.InstancePath)

local SnapshotBuilder = {}

local function captureNode(instance, depth)
    local node = {
        path = InstancePath.getPath(instance),
        name = instance.Name,
        class_name = instance.ClassName,
        children = {},
    }

    if instance:IsA('LuaSourceContainer') then
        local ok, source = pcall(function()
            return instance.Source
        end)
        if ok then
            node.script_source = source
        end
    end

    if depth > 0 then
        for _, child in ipairs(instance:GetChildren()) do
            table.insert(node.children, captureNode(child, depth - 1))
        end
    end

    return node
end

function SnapshotBuilder.buildSnapshot()
    local selected = Selection:Get()
    local nodes = {}
    local selectionPaths = {}

    for _, instance in ipairs(selected) do
        table.insert(selectionPaths, InstancePath.getPath(instance))
        table.insert(nodes, captureNode(instance, 1))
    end

    return {
        captured_at = DateTime.now():ToIsoDate(),
        selection_paths = selectionPaths,
        nodes = nodes,
        diagnostics = {},
    }
end

return SnapshotBuilder
