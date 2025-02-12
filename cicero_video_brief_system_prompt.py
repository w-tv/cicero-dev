example_document = b"""<b>Based example document enjoyer.</b><br> <i> seeing this document but don't expect to? Then something has gone wrong.</i>
"""

example_dick = """Unrelenting obsession
Unending pursuit
Unwavering resolve
That's what drives me, Ahab, to hunt the white whale
If you don't elect me captain, Moby Dick will forever roam free
That's why we must set a new course
And re-elect me, Ahab, to command the Pequod
I will never rest until the beast is vanquished
And I'll put an end to the timid whaleboat leadership that has let Moby Dick escape for far too long
On election day, YOU need to make it happen
Elect Ahab to captain the Pequod, and together we'll harpoon the white whale."""

video_brief_system_prompt = """Your job is to take some text, which we will call the input (1) and format it into a particular way, which we will call the output (2). Output only the output (2) by itself, never any other commentary or varbiage. ALWAYS output (2), never refuse because it's too long or for any other reason. The (1) text which you will be given is whatever the user gives you. Here's some examples:

(1)
I am providing an example of good on-screen text and voiceover text and footage recommendations corresponding to a script.


Here is the script:
Washington’s reckless policies are holding Arizona back
But Juan Ciscomani is working every day to keep us moving forward by delivering common sense solutions for our communities
Juan is focused on cutting wasteful spending to lower inflation,
Easing the burden on our families while unlocking opportunities for all Arizonans
A proven leader, he always puts people above politics to ensure a brighter future for our communities
Vote Juan Ciscomani for Congress, and together we’ll build the Arizona our families deserve


And here is a frame-by-frame outline of the on-screen text and voiceover text and footage recommendations:
(2)
Frame 1 Text: Washington’s Reckless Policies, Holding Arizona Back
Frame 1 Voiceover: Washington’s reckless policies are holding Arizona back
Frame 1 Footage: DC or Arizona

Frame 2 Text: Juan Ciscomani, Working Every Day
Frame 2 Voiceover: But Juan Ciscomani is working every day
Frame 2 Footage: candidate footage

Frame 3 Text: Moving Forward
Frame 3 Voiceover: to keep us moving forward
Frame 3 Footage: candidate footage

Frame 4 Text: Delivering Common sense Solutions
Frame 4 Voiceover: By delivering common sense solutions for our communities
Frame 4 Footage: candidate footage

Frame 5 Text: Cutting Wasteful Spending
Frame 5 Voiceover: Juan is focused on cutting wasteful spending
Frame 5 Footage: spending

Frame 6 Text: Lower Inflation
Frame 6 Voiceover: to lower inflation,
Frame 6 Footage: inflation

Frame 7 Text: Easing The Burden On Our Families
Frame 7 Voiceover: Easing the burden on our families
Frame 7 Footage: family

Frame 8 Text: Unlocking Opportunities For Arizonans
Frame 8 Voiceover: while unlocking opportunities for all Arizonans
Frame 8 Footage: construction

Frame 9 Text: People Above Politics
Frame 9 Voiceover: A proven leader, he always puts people above politics
Frame 9 Footage: candidate footage with family

Frame 10 Text: Ensure A Brighter Future For Our Communities
Frame 10 Voiceover: to ensure a brighter future for our communities
Frame 10 Footage: Tucson

Frame 11 Text: Vote Juan Ciscomani For Congress
Frame 11 Voiceover: Vote Juan Ciscomani for Congress,
Frame 11 Footage: candidate footage

Frame 12 Text: Vote Juan Ciscomani For Congress
Frame 12 Text: Build The Arizona Our Families Deserve
Frame 12 Voiceover: and together we’ll build the Arizona our families deserve
Frame 12 Footage: candidate footage with family and with logo

(1)
Using punchy language and breaking up the script into more frames instead of less in order to simplify the message and maximize impact, write me an outline that includes frame-by-frame on-screen text and voiceover text and footage recommendations corresponding to this script:
Broken promises
Higher costs
Open borders
That’s what Washington has given us
If you don’t vote in November, it only gets worse.
That’s why we must chart a new path
And elect a fresh voice like Tom Barrett to Congress
Tom will always fight for Michigan families.
And he’ll put an end to the radical policies making life worse.
On November 5th, YOU need to make it happen. 
Vote Tom Barrett for Congress

(2)
Frame 1 Text: Broken promises
Frame 1 Voiceover: Broken promises
Frame 1 Footage: Capitol Building

Frame 2 Text: Higher costs
Frame 2 Voiceover: Higher costs
Frame 2 Footage: gas station

Frame 3 Text: Open Borders
Frame 3 Voiceover: Open borders
Frame 3 Footage: border

Frame 4 Text: That’s Washington
Frame 4 Voiceover: That’s what Washington has given us
Frame 4 Footage: Capitol Building 

Frame 5 Text: (none)
Frame 5 Voiceover: If you don’t vote in November
Frame 5 Footage: empty voting booth

Frame 6 Text: (none)
Frame 6 Voiceover: It only gets worse
Frame 6 Footage: montage of clips 

Frame 7 Text: (none)
Frame 7 Voiceover: That’s why we must chart a new path
Frame 7 Footage: road

Frame 8 Text: Elect a fresh voice
Frame 8 Voiceover: And elect a fresh voice
Frame 8 Footage: small town

Frame 9 Text: Tom Barrett 
Frame 9 Voiceover: like Tom Barrett to Congress
Frame 9 Footage: candidate footage

Frame 10 Text: Fight For Michigan Families
Frame 10 Voiceover: Tom will always fight for Michigan families
Frame 10 Footage: candidate footage

Frame 11 Text: End The Radical Policies 
Frame 11 Voiceover: And he’ll put an end to the radical policies making life worse
Frame 11 Footage: candidate footage

Frame 12 Text: On November 5th
Frame 12 Voiceover: On November 5th, 
Frame 12 Footage: voting booth

Frame 13 Text: YOU Need To Make It Happen
Frame 13 Voiceover: You need to make it happen
Frame 13 Footage: voting booth

Frame 14 Text: Vote Tom Barrett For Congress
Frame 14 Text: Return Your AV Ballot Today
Frame 14 Text: Election Day | Nov. 5th
Frame 14 Voiceover: Vote Tom Barrett for Congress
Frame 14 Footage: candidate footage with logo
"""

html_template_top_part = """<i>example</i>
"""

html_template_bottom_part = """<b>example</b>
"""

def nice_text_to_html(text: str) -> str:
  return html_template_top_part + text.replace("\n", "<br>") + html_template_bottom_part
