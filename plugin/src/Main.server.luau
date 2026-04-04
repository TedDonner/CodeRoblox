local PluginHandle = plugin

local AgentClient = require(script.Plugin.AgentClient)
local OperationApplier = require(script.Plugin.OperationApplier)
local Settings = require(script.Plugin.Settings)
local SnapshotBuilder = require(script.Plugin.SnapshotBuilder)

local state = {
    agentUrl = Settings.get(PluginHandle, 'agent_url', 'http://127.0.0.1:8787'),
    projectRoot = Settings.get(PluginHandle, 'project_root', ''),
    sessionId = Settings.get(PluginHandle, 'session_id', nil),
    polling = false,
}

local toolbar = PluginHandle:CreateToolbar('CodeRoblox')
local toggleButton = toolbar:CreateButton('CodeRoblox', 'Open the CodeRoblox control panel.', '')

local widgetInfo =
    DockWidgetPluginGuiInfo.new(Enum.InitialDockState.Left, true, false, 360, 260, 300, 220)

local widget = PluginHandle:CreateDockWidgetPluginGui('CodeRobloxWidget', widgetInfo)
widget.Title = 'CodeRoblox'

local root = Instance.new('Frame')
root.Name = 'Root'
root.Size = UDim2.fromScale(1, 1)
root.BackgroundTransparency = 1
root.Parent = widget

local layout = Instance.new('UIListLayout')
layout.Padding = UDim.new(0, 8)
layout.HorizontalAlignment = Enum.HorizontalAlignment.Center
layout.VerticalAlignment = Enum.VerticalAlignment.Top
layout.FillDirection = Enum.FillDirection.Vertical
layout.Parent = root

local padding = Instance.new('UIPadding')
padding.PaddingTop = UDim.new(0, 12)
padding.PaddingLeft = UDim.new(0, 12)
padding.PaddingRight = UDim.new(0, 12)
padding.PaddingBottom = UDim.new(0, 12)
padding.Parent = root

local title = Instance.new('TextLabel')
title.Size = UDim2.new(1, 0, 0, 28)
title.BackgroundTransparency = 1
title.TextXAlignment = Enum.TextXAlignment.Left
title.Font = Enum.Font.BuilderSansBold
title.TextSize = 20
title.Text = 'CodeRoblox Agent Bridge'
title.Parent = root

local statusLabel = Instance.new('TextLabel')
statusLabel.Size = UDim2.new(1, 0, 0, 32)
statusLabel.BackgroundTransparency = 1
statusLabel.TextWrapped = true
statusLabel.TextXAlignment = Enum.TextXAlignment.Left
statusLabel.TextYAlignment = Enum.TextYAlignment.Top
statusLabel.Font = Enum.Font.BuilderSans
statusLabel.TextSize = 16
statusLabel.Text = 'Not connected'
statusLabel.Parent = root

local agentUrlBox = Instance.new('TextBox')
agentUrlBox.Size = UDim2.new(1, 0, 0, 32)
agentUrlBox.ClearTextOnFocus = false
agentUrlBox.Font = Enum.Font.Code
agentUrlBox.PlaceholderText = 'http://127.0.0.1:8787'
agentUrlBox.Text = state.agentUrl
agentUrlBox.TextSize = 14
agentUrlBox.Parent = root

local actions = Instance.new('Frame')
actions.Size = UDim2.new(1, 0, 0, 96)
actions.BackgroundTransparency = 1
actions.Parent = root

local actionsLayout = Instance.new('UIListLayout')
actionsLayout.Padding = UDim.new(0, 6)
actionsLayout.FillDirection = Enum.FillDirection.Vertical
actionsLayout.Parent = actions

local function makeButton(label)
    local button = Instance.new('TextButton')
    button.Size = UDim2.new(1, 0, 0, 28)
    button.AutoButtonColor = true
    button.Font = Enum.Font.BuilderSans
    button.TextSize = 15
    button.Text = label
    button.Parent = actions
    return button
end

local connectButton = makeButton('Connect Session')
local snapshotButton = makeButton('Push Snapshot')
local checkpointButton = makeButton('Create Checkpoint')

local function setStatus(message)
    statusLabel.Text = message
end

local function makeClient()
    return AgentClient.new(state.agentUrl)
end

local function ensureSession()
    if state.sessionId ~= nil and state.sessionId ~= '' then
        return state.sessionId
    end

    local response = makeClient():startSession({
        client_name = 'roblox-studio-plugin',
        project_root = state.projectRoot,
        capabilities = {
            snapshot = true,
            queue_polling = true,
            apply_script_patch = true,
            create_instance = true,
            update_properties = true,
            reparent_instance = true,
            delete_instance = true,
        },
    })

    state.sessionId = response.session_id
    Settings.set(PluginHandle, 'session_id', state.sessionId)
    return state.sessionId
end

local function pushSnapshot()
    local sessionId = ensureSession()
    local snapshot = SnapshotBuilder.buildSnapshot()
    makeClient():pushSnapshot(sessionId, snapshot)
    setStatus(string.format('Snapshot pushed for %s', sessionId))
end

local function pollLoop()
    if state.polling then
        return
    end

    state.polling = true
    task.spawn(function()
        while state.polling do
            if state.sessionId ~= nil and state.sessionId ~= '' then
                local ok, batch = pcall(function()
                    return makeClient():nextBatch(state.sessionId)
                end)

                if ok and batch ~= nil and batch.batch ~= nil then
                    local batchPayload = batch.batch
                    if batchPayload ~= nil then
                        local outcomes = OperationApplier.applyBatch(batchPayload.operations)
                        local success, err = pcall(function()
                            makeClient():reportBatchResult(
                                state.sessionId,
                                batchPayload.batch_id,
                                outcomes
                            )
                        end)
                        if success then
                            setStatus(string.format('Applied batch %s', batchPayload.batch_id))
                        else
                            setStatus(string.format('Failed to report batch result: %s', err))
                        end
                    end
                elseif not ok then
                    setStatus(string.format('Polling failed: %s', batch))
                end
            end
            task.wait(2)
        end
    end)
end

toggleButton.Click:Connect(function()
    widget.Enabled = not widget.Enabled
end)

agentUrlBox.FocusLost:Connect(function(enterPressed)
    if not enterPressed then
        return
    end

    state.agentUrl = agentUrlBox.Text
    Settings.set(PluginHandle, 'agent_url', state.agentUrl)
    setStatus(string.format('Agent URL set to %s', state.agentUrl))
end)

connectButton.MouseButton1Click:Connect(function()
    local ok, result = pcall(function()
        local sessionId = ensureSession()
        state.projectRoot = state.projectRoot ~= '' and state.projectRoot or game.Name
        Settings.set(PluginHandle, 'project_root', state.projectRoot)
        return sessionId
    end)

    if ok then
        setStatus(string.format('Connected as %s', result))
        pollLoop()
    else
        setStatus(string.format('Connect failed: %s', result))
    end
end)

snapshotButton.MouseButton1Click:Connect(function()
    local ok, err = pcall(pushSnapshot)
    if not ok then
        setStatus(string.format('Snapshot failed: %s', err))
    end
end)

checkpointButton.MouseButton1Click:Connect(function()
    local ok, result = pcall(function()
        local sessionId = ensureSession()
        local response = makeClient():createCheckpoint(sessionId, 'manual-plugin-checkpoint')
        return response.checkpoint.checkpoint_id
    end)

    if ok then
        setStatus(string.format('Checkpoint created: %s', result))
    else
        setStatus(string.format('Checkpoint failed: %s', result))
    end
end)
