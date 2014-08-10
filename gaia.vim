" Vim syntax file
"
" In ~/.vim/scripts.vim:
" if expand('%:p:h:h') =~ '/aiyo/tasks'
"   setfiletype gaia
" endif
"
if version < 600
  syntax clear
elseif exists("b:current_syntax")
  finish
endif
let b:current_syntax = "tasks"
"set nowrap
set wrap

" shut case off
syn case ignore

syn keyword hold onhold hold paused contained
syn keyword permanent permanent contained
syn keyword header header contained
syn keyword flow sequential parallel contained
syn keyword completed completed contained
syn keyword priority ! !! !!! contained
syn keyword wait wait contained
syn keyword waitonrepeat waitonrepeat contained
syn keyword avoidweekends avoidweekends contained
syn keyword current current contained
"syn match wait /\<wait\w*/ contained
syn match repeating /\(\(every\|after\)\w*\|random\|hourly\|daily\|weekly\|fortnightly\|monthly\|annually\|biennially\|decennially\)/ contained
syn match expire /\<expire\w*/ contained
syn match checklist /=[^ ]*/ contained
syn match alarm /![^ ]*/ contained

syn keyword due today tomorrow contained
syn keyword due monday tuesday wednesday thursday friday saturday sunday contained
syn keyword due mon tue tues wed thu thur thurs fri sat sun contained

syntax match due /\d*\(\day\|week\|month\|year\)s*/ contained

syntax match due /\<\d\{6}\>/ contained
syntax match due /\<\d\{10}\>/ contained
syntax match start /\<\w\+:/me=e-1 contained
syn match divider /:/ contained

syntax cluster options contains=hold,permanent,flow,priority,wait,waitonrepeat,completed,repeating,expire,checklist,alarm,due,start,divider,header,journalref,avoidweekends,current

syntax cluster others contains=journalref,href

syntax match journalref /\<entry\[[0-9,]\+\]/ contains=journalkey,journalend,journaldate,journaldivider transparent
syntax match journalkey  /entry\[/ contained contains=NONE nextgroup=journaldate
syntax match journaldate /\d\{14}/ contained contains=NONE nextgroup=journalend,journaldivider
syntax match journalend  /\]/ contained contains=NONE
syntax match journaldivider  /,/ contained contains=NONE
hi journalkey ctermfg=darkgray cterm=none
hi journaldate ctermfg=darkblue cterm=none
hi journalend ctermfg=darkgray cterm=none
hi journaldivider ctermfg=darkgray cterm=none

syntax match href /\<http[^ ]*\>/ contained
hi href ctermfg=darkgray cterm=underline


hi hold ctermfg=darkblue cterm=none
hi permanent ctermfg=darkmagenta cterm=none
hi flow ctermfg=darkmagenta cterm=none
hi priority ctermbg=red cterm=none
hi wait ctermfg=darkmagenta cterm=none
hi waitonrepeat ctermfg=darkmagenta cterm=none
hi repeating ctermfg=darkgreen cterm=none
hi expire ctermfg=darkred cterm=none
hi checklist ctermfg=darkyellow cterm=none
hi completed ctermfg=green cterm=none
hi alarm ctermfg=darkred cterm=none
hi header ctermfg=darkred cterm=none
hi avoidweekends ctermfg=darkmagenta cterm=none
hi current ctermfg=darkmagenta cterm=none

hi start ctermfg=darkcyan cterm=none
hi due ctermfg=darkblue cterm=none
hi divider ctermfg=darkgray cterm=none

syntax region spaces start=/  /ms=s end=/  /me=e contains=NONE contained oneline
syntax region option start=/  [^ ]/ms=e end=/$/me=s-1 contains=@options,@others contained oneline

syntax region indent0 start=/^[^ ]/ms=e-1      end=/^[^ ]/me=s-1 contains=indent1,note0,title0 transparent
syntax region title0  start=/^[^ ]/ms=e-1      end=/$/me=s-1 contained oneline contains=name0,spaces,option nextgroup=note0 transparent keepend
syntax region name0   start=/^[^ ]/ms=s        end=/\(  \|$\)/me=s-1 contained oneline nextgroup=spaces contains=@others
syntax region note0   start=/^ \{4}[^ ]/ms=e-1 end=/^ \{,2}[^ ]/me=s-1 contained contains=@others

syntax region indent1 start=/^ \{2}[^ ]/ms=s   end=/^ \{,2}[^ ]/me=s-1 contains=indent2,note1,title1 contained transparent
syntax region title1  start=/^ \{2}[^ ]/ms=s   end=/$/me=s-1 contained oneline contains=name1,spaces,option nextgroup=note1 transparent keepend
syntax region name1   start=/^ \{2}[^ ]/ms=s   end=/\(  \|$\)/me=s-1 contained oneline nextgroup=spaces contains=@others
syntax region note1   start=/^ \{6}[^ ]/ms=e-1 end=/^ \{,4}[^ ]/me=s-1 contained contains=@others

syntax region indent2 start=/^ \{4}[^ ]/ms=s   end=/^ \{,4}[^ ]/me=s-1 contains=indent3,note2,title2 contained transparent
syntax region title2  start=/^ \{4}[^ ]/ms=s   end=/$/me=s-1 contained oneline contains=name2,spaces,option nextgroup=note2 transparent keepend
syntax region name2   start=/^ \{4}[^ ]/ms=s   end=/\(  \|$\)/me=s-1 contained oneline nextgroup=spaces contains=@others
syntax region note2   start=/^ \{8}[^ ]/ms=e-1 end=/^ \{,6}[^ ]/me=s-1 contained contains=@others

syntax region indent3 start=/^ \{6}[^ ]/ms=s    end=/^ \{,6}[^ ]/me=s-1 contains=indent4,note3,title3 contained transparent
syntax region title3  start=/^ \{6}[^ ]/ms=s    end=/$/me=s-1 contained oneline contains=name3,spaces,option nextgroup=note3 transparent keepend
syntax region name3   start=/^ \{6}[^ ]/ms=s    end=/\(  \|$\)/me=s-1 contained oneline nextgroup=spaces contains=@others
syntax region note3   start=/^ \{10}[^ ]/ms=e-1 end=/^ \{,8}[^ ]/me=s-1 contained contains=@others

syntax region indent4 start=/^ \{8}[^ ]/ms=s    end=/^ \{,8}[^ ]/me=s-1 contains=indent5,note4,title4 contained transparent
syntax region title4  start=/^ \{8}[^ ]/ms=s    end=/$/me=s-1 contained oneline contains=name4,spaces,option nextgroup=note4 transparent keepend
syntax region name4   start=/^ \{8}[^ ]/ms=s    end=/\(  \|$\)/me=s-1 contained oneline nextgroup=spaces contains=@others
syntax region note4   start=/^ \{12}[^ ]/ms=e-1 end=/^ \{,10}[^ ]/me=s-1 contained contains=@others

syntax region indent5 start=/^ \{10}[^ ]/ms=s   end=/^ \{,10}[^ ]/me=s-1 contains=indent6,note5,title5 contained transparent
syntax region title5  start=/^ \{10}[^ ]/ms=s   end=/$/me=s-1 contained oneline contains=name5,spaces,option nextgroup=note5 transparent keepend
syntax region name5   start=/^ \{10}[^ ]/ms=s   end=/\(  \|$\)/me=s-1 contained oneline nextgroup=spaces contains=@others
syntax region note5   start=/^ \{14}[^ ]/ms=e-1 end=/^ \{,12}[^ ]/me=s-1 contained contains=@others

"syn match duedate /\d\{6}/ contained
"syn match duedatetime /\d\{10}/ contained

hi name0 ctermfg=white cterm=none
hi name1 ctermfg=white cterm=none
hi name2 ctermfg=white cterm=none
hi name3 ctermfg=white cterm=none
hi name4 ctermfg=white cterm=none
hi name5 ctermfg=white cterm=none

"syntax cluster names contains=name0,name1,name2,name3,name4,name5
"hi names ctermfg=yellow cterm=none

hi note0 ctermfg=darkgray cterm=none
hi note1 ctermfg=darkgray cterm=none
hi note2 ctermfg=darkgray cterm=none
hi note3 ctermfg=darkgray cterm=none
hi note4 ctermfg=darkgray cterm=none
hi note5 ctermfg=darkgray cterm=none


" vim: ts=8 sw=2
