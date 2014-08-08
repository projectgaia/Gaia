Gaia, task list organiser in with Caldav server sync.
 
Copyright (C) 2013-2014 Dr Adam S. Candy.
Dr Adam S. Candy, contact@gaiaproject.org
 
This file is part of the Gaia project.

Gaia is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

Gaia is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with Gaia.  If not, see <http://www.gnu.org/licenses/>.

TODO
====

Ideally required, reproduces current setup
------------------------------------------
- Attachments - just put in a journal and link?
- mail hook - just add option to journal to also add task, with linkback?

Wishlist
--------
- Inherit due date & priority for sub tasks?  Difficulty propagating back up on caldav change?
- Lose 'inbox', switch to default list in each group
- Cleaner way to change title in caldav - a option?  *'  title:New title given here'*
- titleoption changes that could remove/affect caldav - change self.updated?  e.g. for due, that then changes start date too, taking it out of current focus (OK right now, but needs second run?)
- Allow +1week *added* on to times on file, which are then expanded here (today, tomorrow done) 
- Allow start to be a reference to completion/start of another task?
- Defer - special keyword for defer one off - i.e. start returns to normal once comepleted

Possible robustness fixes required
----------------------------------
- *De-duplicate* a bit over-zealous?  Couple of passes deals with it?
- Solve race condition (e.g. when changing due and alarm times in caldav client) - use sequence?, check less often?
- Consistency check? aiyo <-> caldav, check no duplicates? DONE, aiyo needs improvement, but workable and robust
- Calendars of the same name overwritten in the backup code


Done?
-----
- Have key words in caldav sorted on same run, not next - currently added to aiyo and processed, then on next run propagate changes to caldav
- Recur tasks hit sanity check - need to remove from active?  Completing a checklist/auxlist header - need to complete/remove children here (from active and caldav) to avoid sanity and sorting out on next run


Note when adding features on the aiyo lines that can be set in the caldav, these need to be interpreted by the FileTodo call in add of CalTodo - i.e. add them to the parsed line.
translate: temporary caldav lists/aux lists - need to add to reformat in CalTodo?


