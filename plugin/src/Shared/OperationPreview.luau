local OperationPreview = {}

function OperationPreview.summarize(operations, protocol)
    local adapter = protocol
        or {
            riskForKind = function()
                return 'low'
            end,
            isDestructive = function()
                return false
            end,
        }

    local summary = {
        total = #operations,
        low = 0,
        medium = 0,
        high = 0,
        destructive = 0,
    }

    for _, operation in ipairs(operations) do
        local risk = adapter.riskForKind(operation.kind)
        summary[risk] += 1
        if adapter.isDestructive(operation.kind) then
            summary.destructive += 1
        end
    end

    return summary
end

return OperationPreview
