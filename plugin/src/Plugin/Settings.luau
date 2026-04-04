local Settings = {}

local KEY_PREFIX = 'coderoblox.'

function Settings.get(pluginHandle, key, defaultValue)
    local value = pluginHandle:GetSetting(KEY_PREFIX .. key)
    if value == nil then
        return defaultValue
    end
    return value
end

function Settings.set(pluginHandle, key, value)
    pluginHandle:SetSetting(KEY_PREFIX .. key, value)
end

return Settings
