local HttpClient = require(script.Parent.HttpClient)

local AgentClient = {}
AgentClient.__index = AgentClient

function AgentClient.new(baseUrl)
    return setmetatable({
        http = HttpClient.new(baseUrl),
    }, AgentClient)
end

function AgentClient:startSession(payload)
    return self.http:post('/api/sessions', payload)
end

function AgentClient:pushSnapshot(sessionId, snapshot)
    return self.http:post('/api/snapshots', {
        session_id = sessionId,
        snapshot = snapshot,
    })
end

function AgentClient:createCheckpoint(sessionId, label)
    return self.http:post('/api/checkpoints', {
        session_id = sessionId,
        label = label,
    })
end

function AgentClient:nextBatch(sessionId)
    return self.http:get(string.format('/api/operations/next?session_id=%s', sessionId))
end

function AgentClient:reportBatchResult(sessionId, batchId, outcomes)
    return self.http:post('/api/operations/result', {
        session_id = sessionId,
        batch_id = batchId,
        outcomes = outcomes,
    })
end

return AgentClient
