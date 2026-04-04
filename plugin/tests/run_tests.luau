local specs = {
    require('./PathUtils.spec'),
    require('./Protocol.spec'),
}

local passed = 0

for _, spec in ipairs(specs) do
    spec()
    passed += 1
end

print(string.format('%d Luau spec files passed', passed))
