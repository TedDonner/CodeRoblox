local prompt = script.Parent
local event = game.ReplicatedStorage:WaitForChild("OpenShopGUI")

prompt.Triggered:Connect(function(player)
	-- Sende Nachricht an diesen Spieler, damit das GUI erscheint
	event:FireClient(player)
end)



