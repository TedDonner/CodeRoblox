local PathUtils = require('../src/Shared/PathUtils')

return function()
    assert(PathUtils.normalize('game/Workspace//Part') == 'Workspace/Part')
    assert(
        PathUtils.normalize('ReplicatedStorage\\Modules\\Foo') == 'ReplicatedStorage/Modules/Foo'
    )
    assert(PathUtils.join('Workspace', 'Folder', 'Part') == 'Workspace/Folder/Part')

    local segments = PathUtils.split('/Workspace/Foo/Bar/')
    assert(#segments == 3)
    assert(segments[1] == 'Workspace')
    assert(segments[3] == 'Bar')
end
