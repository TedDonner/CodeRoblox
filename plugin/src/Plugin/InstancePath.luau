local PathUtils = require(script.Parent.Parent.Shared.PathUtils)

local InstancePath = {}

function InstancePath.getPath(instance)
    local segments = {}
    local current = instance

    while current ~= nil and current ~= game do
        table.insert(segments, 1, current.Name)
        current = current.Parent
    end

    return table.concat(segments, '/')
end

function InstancePath.findByPath(path)
    local segments = PathUtils.split(path)
    local current = game

    for _, segment in ipairs(segments) do
        current = current:FindFirstChild(segment)
        if current == nil then
            return nil
        end
    end

    return current
end

return InstancePath
