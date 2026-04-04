local HttpService = game:GetService('HttpService')

local HttpClient = {}
HttpClient.__index = HttpClient

function HttpClient.new(baseUrl)
    return setmetatable({
        baseUrl = string.gsub(baseUrl, '/+$', ''),
    }, HttpClient)
end

function HttpClient:_request(method, path, body)
    local requestOptions = {
        Url = self.baseUrl .. path,
        Method = method,
        Headers = {
            ['Content-Type'] = 'application/json',
        },
    }

    if body ~= nil then
        requestOptions.Body = HttpService:JSONEncode(body)
    end

    local response = HttpService:RequestAsync(requestOptions)
    local decodedBody = nil

    if response.Body ~= '' then
        local ok, value = pcall(function()
            return HttpService:JSONDecode(response.Body)
        end)
        if ok then
            decodedBody = value
        end
    end

    if not response.Success then
        local message = response.StatusMessage
        if decodedBody ~= nil and decodedBody.error ~= nil then
            message = decodedBody.error
        end
        error(message)
    end

    return decodedBody
end

function HttpClient:get(path)
    return self:_request('GET', path, nil)
end

function HttpClient:post(path, body)
    return self:_request('POST', path, body)
end

return HttpClient
