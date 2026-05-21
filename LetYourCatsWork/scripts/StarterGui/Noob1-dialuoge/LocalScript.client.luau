local frame = script.Parent:WaitForChild("Frame")
local event = game.ReplicatedStorage:WaitForChild("OpenShopGUI")
local text  = frame:WaitForChild("TextLabel")

event.OnClientEvent:Connect(function()
	frame.Visible = true
	text.Visible = true
	wait(5)
	frame.Visible = false
	text.Visible = false
end)

