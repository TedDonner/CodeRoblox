local PathUtils = {}

function PathUtils.normalize(path)
    local normalized = string.gsub(path, '\\', '/')
    normalized = string.gsub(normalized, '^game/', '')
    normalized = string.gsub(normalized, '^/', '')
    normalized = string.gsub(normalized, '/+', '/')
    normalized = string.gsub(normalized, '/$', '')
    return normalized
end

function PathUtils.split(path)
    local segments = {}
    local normalized = PathUtils.normalize(path)
    if normalized == '' then
        return segments
    end

    for segment in string.gmatch(normalized, '[^/]+') do
        table.insert(segments, segment)
    end

    return segments
end

function PathUtils.join(...)
    local parts = { ... }
    local joined = table.concat(parts, '/')
    return PathUtils.normalize(joined)
end

return PathUtils
