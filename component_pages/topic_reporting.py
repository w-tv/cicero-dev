#!/usr/bin/env -S streamlit run

import streamlit as st
from databricks import sql
from collections.abc import Iterable
from typing import Any, Sequence
from .prompter import topics_big, load_account_names

import streamlit as st
import pandas as pd
import numpy as np
import altair as alt

def to_sql_tuple_string(x: Sequence[str]) -> str:
  """SQL doesn't like the trailing comma python puts in a singleton tuple, so we can't just use the tuple constructor and then convert that to string; we have to do this instead."""
  if len(x) == 0:
    return "(NULL)" #this is a special case, because SQL doesn't like 'in ()' for some reason
  else:
    quoted = [f"'{x}'" for x in x]
    return f"({', '.join(quoted)})"

def bool_dict_to_string_list(dict_of_strings_to_bool: dict[str, bool]) -> list[str]:
  return [s for s, value in dict_of_strings_to_bool.items() if value]

@st.cache_data() # I decided to memoize this function primarily in order to make development of the graphing go more rapidly, but it's possible that this will cost us an unfortunate amount of RAM if maybe people use this page. So, removing this memoization is something to consider.
def sql_call(query: str, sql_params_dict:dict[str, Any]|None=None) -> list[str]:
  with sql.connect(server_hostname=st.secrets["DATABRICKS_SERVER_HOSTNAME"], http_path=st.secrets["DATABRICKS_HTTP_PATH"], access_token=st.secrets["databricks_api_token"]) as connection: #These secrets should be in the root level of the .streamlit/secrets.toml
    with connection.cursor() as cursor:
      return cursor.execute(query, sql_params_dict).fetchall()

def to_graphable_dict(values: Sequence[Sequence[Any]], x:str='x', y:str='y', color:str='color') -> list[dict[str, Any]]:
  if len(values) == 3: #it's a 3-list of n-lists
    return [{x: values[0][i], y:values[1][i], color:values[2][i]} for i, _ in enumerate(values[0])]
  else:
    return [{x: value[0], y:value[1], color:value[2]} for value in values]

internal_account_name_to_external_account_name = { #many-to-one relationship
  '1776 Action - Twenty Manor (TMA Direct)' : '1776 Action - TMA',
  '1776 Action (TMA)' : '1776 Action - TMA',
  '1776 PAC - Convert Digital (TMA)' : '1776 PAC - TMA',
  'Abbott' : 'Greg Abbott',
  'ACG: Opportunity Matters Fund Action' : 'OMFA',
  'ACG: Trust in the Mission PAC' : 'TIMPAC',
  'ACI - NextAfter (TMA)' : 'ACI - TMA',
  'Adam Laxalt for NV' : 'Adam Laxalt',
  'Adkins, Amanda (KS-03)' : 'Amanda Adkins',
  'Advancing American Freedom' : 'AAF',
  'Aliscia Andrews for Congress (TMA Direct)' : 'Aliscia Andrews - TMA',
  'America First Policy Institute - Convert Digital (TMA)' : 'America First Policy Institute - TMA',
  'America Rising PAC (916)' : 'America Rising PAC - TMA',
  'American Cornerstone Institute - Active Engagement (TMA)' : 'ACI - TMA',
  'American Cornerstone Institute (ACI)' : 'ACI',
  'American Cornerstone Institute (TMA)' : 'ACI - TMA',
  'American Fortitude PAC' : 'American Fortitude PAC - TMA',
  'American Leadership Action: 824 Solutions' : 'American Leadership Action - TMA',
  'American Principles Project - Olympic Media (TMA)' : 'American Principles Project - TMA',
  'Americans for Prosperity - Action' : 'AFP Action',
  'Anderson, Derrick (VA-07)' : 'Derrick Anderson',
  'Andy Biggs - Olympic Media (TMA)' : 'Andy Biggs - TMA',
  'Anna Paulina Luna - Campaign Inbox (TMA)' : 'Anna Paulina Luna - TMA',
  'Arizona GOP - National Public Affairs (TMA Direct)' : 'Arizona GOP - TMA',
  'Barr, Andy (KY-06)' : 'Andy Barr',
  'Barrasso' : 'John Barrasso',
  'Barrett, Tom (MI-07)' : 'Tom Barrett',
  'Barry Moore for Congress - National Public Affairs (TMA Direct)' : 'Barry Moore - TMA',
  'Ben Carson: ACI (TMA)' : 'Ben Carson - TMA',
  'Bice' : 'Stephanie Bice',
  'BILL PAC' : 'BILL PAC',
  'BILL PAC' : 'Bill Eigel',
  'Binkley for President - JLoft Company (TMA Direct)' : 'Binkley for President - TMA',
  'Blackburn TVF' : 'Marsha Blackburn',
  'Blaine for Congress' : 'Blaine Luetkemeyer',
  'Bo Hines for Congress - National Public Affairs (TMA Direct)' : 'Bo Hines - TMA',
  'Bob Latta' : 'Bob Latta',
  'Britt - Convert Digital (TMA)' : 'Katie Britt - TMA',
  'Britt - Convergence (916)': 'Katie Britt - TMA',
  'Katie Britt for Senate (AL-Sen) (Convert Digital)': 'Katie Britt - TMA',
  'Brnovich for AZ Senate' : 'Mark Brnovich',
  'Brown, Sam (NV-Sen) (Convert Digital)' : 'Sam Brown',
  'Budd (TAG)' : 'Ted Budd',
  'Burgess, Michael (TX-26)' : 'Michael Burgess',
  'Byron Donalds for Congress - Campaign Inbox (TMA)' : 'Byron Donalds - TMA',
  'Calvert for Congress' : 'Ken Calvert',
  'Cameron Sexton for State Rep (TMA Direct)' : 'Cameron Sexton - TMA',
  'Carl, Jerry (AL-01)' : 'Jerry Carl',
  'Carla Spalding - Olympic Media (TMA)' : 'Carla Spalding - TMA',
  'Cassidy' : 'Bill Cassidy',
  'Catalina for Congress (Validus LLC)' : 'Catalina Lauf',
  'CatholicVote - Frontline Strategies (TMA)' : 'CatholicVote - TMA',
  'CAVPAC' : 'CAVPAC',
  'Chambers for Indiana - IMGE (TMA)' : 'Brad Chambers - TMA',
  'Chief Vitiello for Senate - National Public Affairs (TMA Direct)' : 'Chief Vitiello - TMA',
  'Chip Roy for Congress - Frontline Strategies (TMA)' : 'Chip Roy - TMA',
  'Chris “Mookie” Walker for WV-02 (TMA Direct)' : 'Chris Walker - TMA',
  'Chuck Hand - Olympic Media (TMA)' : 'Chuck Hand - TMA',
  'Cicely Davis - Olympic Media (TMA)' : 'Cicely Davis - TMA',
  'Ciscomani, Juan (AZ-06)' : 'Juan Ciscomani',
  'Citizens for a Greater Georgia' : 'Greater Georgia',
  'Citizens United (TMA)' : 'Citizens United - TMA',
  'CLF - Convergence (TMA)' : 'CLF - TMA',
  'CLF (916 - Convergence)' : 'CLF - TMA',
  'CLF (TMA)' : 'CLF - TMA',
  'Committee to Elect Jennifer-Ruth Green' : 'Jennifer-Ruth Green',
  'Committee to Elect Ryan Weld - National Public Affairs (TMA Direct)' : 'Ryan Weld - TMA',
  'Congressional Leadership Fund' : 'CLF',
  'Convert Digital: Jay Collins' : 'Jay Collins',
  'Convert Digital: Madison Gesiotto Gilbert' : 'Madison Gesiotto Gilbert',
  'Cotton' : 'Tom Cotton',
  'Crane for Congress' : 'Eli Crane',
  'CSS: Black Bear PAC' : 'Black Bear PAC',
  'CSS: Georgia Values Fund' : 'George Values Fund',
  'CSS: Honor Pennsylvania' : 'Honor Pennsylvania',
  'CSS: Keystone Renewal PAC' : 'Keystone Renewal PAC',
  'CSS: Keystone Renewal PAC' : 'Keystone Renewal',
  'CSS: Opportunity Matters Fund' : 'OMF',
  'CSS: Opportunity Matters Fund Action' : 'OMFA',
  'CSS: Protecting Ohio Values PAC' : 'Protecting Ohio Values PAC',
  'CSS: Stand for New Hampshire PAC' : 'Stand for New Hampshire PAC',
  'David Yost for Ohio' : 'David Yost',
  'Davidson for Congress (TMA Direct)' : 'Warren Davidson - TMA',
  'Davis' : 'Rodney Davis',
  'De Gregorio, Nick (NJ-05)' : 'Nick De Gregorio',
  'De La Cruz, Monica (TX-15)' : 'Monica De La Cruz',
  'Defense of Freedom PAC' : 'Defense of Freedom PAC',
  'DeWine Husted for Ohio - Right Digital (916)' : 'Mike DeWine - TMA',
  'DMS: Grassroots Action Fund' : 'Grassroots Action Fund',
  'DMS: NVAF' : 'NVAF',
  'DMS: Protect and Defend America' : 'PADA',
  'Dorow, Jennifer (WI-Supreme Court)' : 'Jennifer Dorow',
  'Doug Burgum for America - RedSpark Strategy (TMA)' : 'Doug Burgum - TMA',
  'Doug Mastriano - Olympic Media (TMA)' : 'Doug Mastriano - TMA',
  'Downing for Congress' : 'Troy Downing',
  'Duke, Brady (FL-07)' : 'Brady Duke',
  'Duty First Nevada' : 'Duty First Nevada',
  'Eigel, Bill (MO-Gov)' : 'Bill Eigel',
  'Elder for America (TMA Direct)' : 'Larry Elder - TMA',
  'Elect Common Sense - National Public Affairs (TMA Direct)' : 'Elect Common Sense - TMA',
  'Elect Gabe Evans - OnMessage (TMA Direct)' : 'Gabe Evans - TMA',
  'Elise for Congress' : 'Elise Stefanik',
  'Elise Stefanik - Olympic Media (TMA)' : 'Elise Stefanik - TMA',
  'Ellzey' : 'Jake Ellzey',
  'Emmer, Tom (MN-06)' : 'Tom Emmer',
  'Ernst' : 'Joni Ernst',
  'Evans, Jake (GA-06)' : 'Jake Evans',
  'FL GOP - The Aventine Group (TMA Direct)' : 'FL GOP - TMA',
  'Flores, Mayra (TX-34)' : 'Mayra Flores',
  'Frank LaRose for Ohio - Right Digital (916)' : 'Frank LaRose - TMA',
  'Franklin, Scott (FL-15)' : 'Scott Franklin',
  'Friends of Andrew Koenig (TMA Direct)' : 'Andrew Koenig - TMA',
  'Friends of Kathy Barnette (TMA)' : 'Kathy Barnette - TMA',
  'Friends of Mark Robinson (TMA Direct)' : 'Mark Robinson - TMA',
  'Friends of Mark Robinson (TMA)' : 'Mark Robinson - TMA',
  'Friends of Ron DeSantis (TMA Direct)' : 'Ron DeSantis - TMA',
  'Garbarino, Andrew (NY-02)' : 'Andrew Garbarino',
  'Garcia for Virginia (TMA Direct)' : 'Eddie Garcia - TMA',
  'Garcia, Cassy (TX-28)' : 'Cassy Garcia',
  'Garcia, Eddie (VA-00)' : 'Eddie Garcia',
  'George Logan for Congress' : 'George Logan',
  'Gilberry, Wallace (AL-02)' : 'Wallace Gilberry',
  'Gonzales' : 'Tony Gonzales',
  'Grassley (TAG)' : 'Chuck Grassley',
  'Great America Committee' : 'Great America Committee',
  'Great America Committee (TMA)' : 'Great America Committee - TMA',
  'Great Opportunity Party' : 'Great Opportunity Party',
  'Greater Georgia' : 'Greater Georgia',
  'Hageman for Wyoming - National Public Affairs (TMA Direct)' : 'Harriet Hageman - TMA',
  'Hagerty' : 'Bill Hagerty',
  'Harshbarger, Diana (TN-01)' : 'Diana Harshbarger',
  'Hayslett, Kevin (FL-13)' : 'Kevin Hayslett',
  'HCT - Convert Digital (916)' : 'HCT - TMA',
  'Hellfire PAC - Convert Digital (TMA)' : 'Hellfire PAC - TMA',
  'Heritage Action for America - IMGE (TMA)' : 'Heritage Action - TMA',
  'HeroBox - DonorBureau (TMA)' : 'HeroBox - TMA',
  'Herschel Walker - DonorBureau (TMA)' : 'Herschel Walker - TMA',
  'Hinson' : 'Ashley Hinson',
  'Hoskins, Denny (MO-State Sen)' : 'Denny Hoskins',
  'House GOP Battleground Fund - WaMa Strategies (TMA)' : 'House GOP Battleground Fund - TMA',
  'Hung Cao - Onmessageinc (TMA)' : 'Hung Cao - TMA',
  'Hung Cao for Congress - Onmessageinc (916)' : 'Hung Cao - TMA',
  'Hung Cao for Congress (TMA)' : 'Hung Cao - TMA',
  'Hung Cao for Senate - OnMessage Inc (TMA Direct)' : 'Hung Cao - TMA',
  'Hunt (On Message Inc)' : 'Jeremy Hunt - TMA',
  'Hunt for Congress - Campaign Inbox (TMA)' : 'Jeremy Hunt - TMA',
  'Illinois Campaign - Richard Irvin for Governor' : 'Richard Irvin',
  'Illinois Campaign - Steve Kim for Attorney General' : 'Steve Kim',
  'Iowans for Zach Nunn' : 'Zach Nunn',
  'Iowans for Zach Nunn - National Public Affairs (TMA Direct)' : 'Zach Nunn - TMA',
  'J.D. Vance - TAG (TMA)' : 'JD Vance - TMA',
  'James Comer - WaMa Strategies (TMA)' : 'James Comer - TMA',
  'James for Congress (MI-10)' : 'John James',
  'Jason Smith for Congress - National Public Affairs (TMA Direct)' : 'Jason Smith - TMA',
  'Jay Collins - Convert Digital (TMA)' : 'Jay Collins - TMA',
  'Jay Collins for Congress (TMA)' : 'Jay Collins - TMA',
  'Jeanine Lawson for Congress' : 'Jeanine Lawson',
  'Jeff Landry (LA Gov) (TMA Direct)' : 'Jeff Landry - TMA',
  'Jersey 1st' : 'Jersey 1st',
  'Jesse Jensen - Convergence (916)' : 'Jesse Jensen - TMA',
  'Jim Jordan - Olympic Media (TMA)' : 'Jim Jordan - TMA',
  'Jim Jordan for Congress (TMA)' : 'Jim Jordan - TMA',
  'Jim Nelson for Congress - OnMessage Inc (TMA Direct)' : 'Jim Nelson - TMA',
  'Joe Arpaio for Fountain Hills Mayor (TMA Direct)' : 'Joe Arpaio - TMA',
  'John Bolton PAC' : 'John Bolton PAC',
  'John Gibbs - Olympic Media (TMA)' : 'John Gibbs - TMA',
  'John James' : 'John James - TMA',
  'John James for Congress (TMA-916)' : 'John James - TMA',
  'John Teichert for Senate' : 'John Teichert',
  'Johnson, Drew (NV-03)' : 'Drew Johnson',
  'Josh Hawley Victory Committee - Onmessageinc (TMA)' : 'Josh Hawley - TMA',
  'Kari Lake - Olympic Media (TMA)' : 'Kari Lake - TMA',
  'Kari Lake - TAG (TMA)' : 'Kari Lake - TMA',
  'Karoline Leavitt For Congress - Olympic Media (TMA)' : 'Karoline Leavitt - TMA',
  'Karrin for Arizona' : 'Karrin Taylor Robson',
  'Kemp for Governor (TMA)' : 'Brian Kemp - TMA',
  'Kennedy (TAG)' : 'John Kennedy - TMA',
  'Kiggans, Jen (VA-02)' : 'Jen Kiggans',
  'Kim Reynolds' : 'Kim Reynolds',
  'Koenig, Andrew (MO-Treasurer)' : 'Andrew Koenig',
  'Kristi Noem for Governor (TMA)' : 'Kristi Noem - TMA',
  'KRISTI PAC - The Aventine Group (TMA Direct)' : 'Kristi Noem - TMA',
  'KSC: SFA Fund, Inc.' : 'Nikki Haley',
  'LaHood, Marc (Murphy Nasica)' : 'Marc LaHood',
  'Lamon for Senate (TAG)' : 'Jim Lamon',
  'Lance Gooden for Congress Committee - Olympic Media (TMA)' : 'Lance Gooden - TMA',
  'LaRose, Frank (OH)' : 'Frank LaRose',
  'LaTurner, Jake' : 'Jake LaTurner',
  'Lauren Boebert - Frontline Strategies (TMA)' : 'Lauren Boebert - TMA',
  'Leadership for Ohio Fund, LLC' : 'Leadership for Ohio',
  'Luttrell-TX-08' : 'Morgan Luttrell',
  'Madison for Congress - Convert Digital (TMA)' : 'Madison Gesiotto Gilbert - TMA',
  'Madison Gesiotto Gilbert for Congress (TMA)' : 'Madison Gesiotto Gilbert - TMA',
  'Majority Committee PAC' : 'Kevin McCarthy',
  'Majority Conservative Fund' : 'Kevin McCarthy',
  'Majority Maker Fund' : 'Majority Maker Fund',
  'Marjorie Taylor Greene - WaMa Strategies (TMA)' : 'Marjorie Taylor Greene - TMA',
  'Maryott' : 'Brian Maryott',
  'Mazi Pilip for Congress' : 'Mazi Pilip',
  'McCarthy-CA-23' : 'Kevin McCarthy',
  'McCarthy Victory Fund' : 'Kevin McCarthy',
  'McConnell' : 'Mitch McConnell',
  'McCormick for Senate - RedSpark Strategy (TMA)' : 'David McCormick - TMA',
  'McCormick, David (PA-00)' : 'David McCormick',
  'McMorris WFF' : 'Cathy McMorris Rodgers',
  'McSwain for Governor' : 'Bill McSwain',
  'MEGOP IE' : 'MEGOP',
  'Meijer, Peter (MI-03)' : 'Peter Meijer',
  'Mercury One (TMA Direct)' : 'Mercury One - TMA',
  'Mercury One (TMA)' : 'Mercury One - TMA',
  'Mercy Chefs - Grassroots Action (TMA Direct)' : 'Mercy Chefs - TMA',
  'Mercy Chefs - Grassroots Action (TMA)' : 'Mercy Chefs - TMA',
  'Mercy Chefs (TMA-916)' : 'Mercy Chefs - TMA',
  'Michael Waltz for Congress - Onmessageinc (TMA)' : 'Michael Waltz - TMA',
  'Michael Waltz for Congress- Onmessageinc (916)' : 'Michael Waltz - TMA',
  'Mike Collins for Congress - National Public Affairs (TMA Direct)' : 'Mike Collins - TMA',
  'Mike France for CT2 - National Public Affairs (TMA Direct)' : 'Mike France - TMA',
  'Mike Johnson (Convergence Digital)' : 'Mike Johnson',
  'Mike Pence' : 'Mike Pence',
  'Mike Waltz - National Media' : 'Mike Waltz',
  'Mo Brooks for Senate (TMA)' : 'Mo Brooks - TMA',
  'Moms for Liberty PAC - Twenty Manor (TMA Direct)' : 'Moms for Liberty - TMA',
  'Mooney for Senate - Campaign Inbox (TMA)' : 'Alexander Mooney - TMA',
  'More Jobs Less Government' : 'More Jobs Less Government',
  'Morrisey 2024' : 'Patrick Morrisey',
  'Mowers for Congress' : 'Matt Mowers',
  'MSS: Great Opportunity Party' : 'Tim Scott',
  'MSS: Tim Scott' : 'Tim Scott',
  'MSS: Tim Scott (Senate)' : 'Tim Scott',
  'MSS: Tim Scott Victory Fund' : 'Tim Scott',
  'Mullin Victory Fund - National Public Affairs (TMA Direct)' : 'Markwayne Mullin - TMA',
  'Mullin, Markwayne (OK-00)' : 'Markwayne Mullin',
  'Murkowski' : 'Lisa Murkowski',
  'My Faith Votes (TMA Direct)' : 'My Faith Votes - TMA',
  'My Faith Votes (TMA)' : 'My Faith Votes - TMA',
  'Nancy Mace (JFC)' : 'Nancy Mace',
  'NCPD - DonorBureau (TMA)' : 'NCPD - TMA',
  'Nick Begich for Alaska - National Public Affairs (TMA Direct)' : 'Nick Begich - TMA',
  'Nikki Haley for President' : 'Nikki Haley',
  'Nine PAC (TMA Direct)' : 'Nine PAC - TMA',
  'Noem (TMA Direct)' : 'Kristi Noem - TMA',
  'Norber for Congress - National Public Affairs (TMA Direct)' : 'Daniel Norber - TMA',
  'November Victory Fund' : 'Tim Scott',
  'NRCC' : 'NRCC',
  'NRSC (TMA)' : 'NRSC - TMA',
  'Ohio Clean Water Fund - WAMA Strategies (TMA)' : 'Ohio Clean Water Fund - TMA',
  'Oorah! PAC' : 'Oorah PAC',
  'Orlando Sonza for Congress (TMA Direct)' : 'Orlando Sonza - TMA',
  'Ortagus, Morgan (TN-05)' : 'Morgan Ortagus',
  'PA Rising' : 'PA Rising',
  'Parent Voices Matter - National Public Affairs (TMA Direct)' : 'Parent Voices Matter - TMA',
  'Perdue for Governor, Inc.' : 'David Purdue',
  'Pfluger, August (TX-11)' : 'August Pfluger',
  'Poliquin, Bruce (ME-02)' : 'Bruce Poliquin',
  'Protecting Americans Project Action Fund' : 'Protecting Americans Project Action',
  'Qualls, Kendall (MN-00)' : 'Kendall Qualls',
  'Rahm for Congress - National Public Affairs (TMA Direct)' : 'Tayler Rahm - TMA',
  'Rand Paul - IMGE (TMA)' : 'Rand Paul - TMA',
  'Rand Paul for Senate (TMA)' : 'Rand Paul - TMA',
  'Raptor PAC' : 'Raptor PAC',
  'Red Renaissance - Olympic Media (TMA)' : 'Red Renaissance - TMA',
  'Republican Jewish Coalition' : 'RJC',
  'Republican National Committee (TMA)' : 'RNC - TMA',
  'Reschenthaler, Guy (PA-14)' : 'Guy Reschenthaler',
  'Retire or Lose' : 'NRCC',
  'RGA' : 'RGA',
  'RGA (TMA)' : 'RGA - TMA',
  'Richard Hudson for Congress - OnMessage Inc (TMA Direct)' : 'Richard Hudson - TMA',
  'Rick Scott - Onmessageinc (916)' : 'Rick Scott - TMA',
  'Rick Scott for Senate - Onmessageinc (TMA)' : 'Rick Scott - TMA',
  'RNC (TMA Direct)' : 'RNC - TMA',
  'Robinson, Mark (NC-Gov)' : 'Mark Robinson',
  'Roca for Congress - National Public Affairs (TMA Direct)' : 'Mariela Roca - TMA',
  'Rogers for Senate (Convert Digital)' : 'Mike Rogers - TMA',
  'Rokita' : 'Todd Rokita',
  'Ron DeSantis' : 'Ron DeSantis - TMA',
  'Ron DeSantis (TMA Direct)' : 'Ron DeSantis - TMA',
  'Ron DeSantis (TMA)' : 'Ron DeSantis - TMA',
  'Ron DeSantis for President (TMA Direct)' : 'Ron DeSantis - TMA',
  'Ron Johnson' : 'Ron Johnson',
  'Ronda Kennedy for Congress (TMA)' : 'Ronda Kennedy - TMA',
  'Ronny Jackson' : 'Ronny Jackson',
  'Rose, John (TN-06)' : 'John Rose',
  'RSLC' : 'RSLC',
  'RSLC Victory Fund' : 'RSLC',
  'RSLC Washington PAC' : 'RSLC',
  'Rubio for Senate' : 'Marco Rubio',
  'Rubio Victory Committee' : 'Marco Rubio',
  'RUN Ministries - Grassfire Action (TMA Direct)' : 'RUN Ministries - TMA',
  'Save America PAC - DonorBureau (TMA)' : 'Save America PAC - TMA',
  'Scalise' : 'Steve Scalise',
  'Scharf, Will (MO-AG)' : 'Will Scharf',
  'Scheller, Lisa (PA-07)' : 'Lisa Scheller',
  'Scott Pruitt for Senate (TMA)' : 'Scott Pruitt - TMA',
  'Senate Conservatives Fund (Walker) - TMA' : 'Senate Conservatives Fund - TMA',
  'Serrano, Carolina (NV-01)' : 'Carolina Serrano',
  'Servant Leadership Fund - Onmessageinc (TMA)' : 'Servant Leadership Fund - TMA',
  'Service and Honor JFC' : 'Jake Ellzey',
  'Shadow Warriors Project - Twenty Manor (TMA Direct)' : 'Shadow Warriors Project - TMA',
  'Shirley for Congress - National Public Affairs ( TMA Direct)' : 'Shirley Maia Cusick - TMA',
  'Smiley for Washington' : 'Tiffany Smiley',
  'SOS America PAC - Harris Media LLC (TMA Direct)' : 'SOS America PAC - TMA',
  'Stand for America 501(c)(4)' : 'Nikki Haley',
  'Stand for America PAC' : 'Nikki Haley',
  'State Republican Victory Fund (SRVF)' : 'RSLC',
  'Steel' : 'Michelle Steel',
  'Steven Elliot - Olympic Media (TMA)' : 'Steven Elliot - TMA',
  'Stitt' : 'Kevin Stitt',
  'Taylor Burks for Congress' : 'Taylor Burks',
  'Team Elise - Campaign Inbox (TMA)' : 'Elise Stefanik - TMA',
  'Team Elise - Olympic Media (TMA)' : 'Elise Stefanik - TMA',
  'Team Elise - RedSpark Strategy (TMA)' : 'Elise Stefanik - TMA',
  'Team Emmer' : 'Tom Emmer',
  'Team Mayra (JFC)' : 'Mayra Flores',
  'Team Morrisey' : 'Patrick Morrisey',
  'Team Morrisey - Convergence (TMA)' : 'Patrick Morrisey - TMA',
  'Team Morrisey (TMA)' : 'Patrick Morrisey - TMA',
  'Team Ronny - National Public Affairs (TMA Direct)' : 'Ronny Jackson - TMA',
  'Team Scalise' : 'Steve Scalise',
  'Team Stand for America JFC' : 'Nikki Haley',
  'Teirab, Joe (MN-02)' : 'Joe Teirab',
  'Tenney, Claudia (NY-24)' : 'Claudia Tenney',
  'Texans for Ronny Jackson (TMA Direct)' : 'Ronny Jackson - TMA',
  'The American Dream PAC' : 'The American Dream PAC',
  'The Media Accountability Project (TMA Direct)' : 'Media Accountability Project - TMA',
  'The Media Accountability Project (TMA)' : 'Media Accountability Project - TMA',
  'The Pat Harrigan Committee - OnMessage (TMA Direct)' : 'Pat Harrigan Committee - TMA',
  'The Themis Alliance - Twenty Manor (TMA Direct)' : 'Themis Alliance - TMA',
  'Think BIG America PAC' : 'Think BIG America PAC',
  'Think BIG America PAC (TMA Direct)' : 'Think BIG America PAC - TMA',
  'Thune' : 'John Thune',
  'Tim Scott' : 'Tim Scott',
  'Tina Forte - Olympic Media (TMA)' : 'Tina Forte - TMA',
  'Todd Young' : 'Todd Young',
  'Tom Kean - Flexpoint Media (TMA)' : 'Tom Kean - TMA',
  'Tom Royals For Congress' : 'Tom Royals',
  'Trump Save America - Campaign Inbox (TMA)' : 'Trump Save America - TMA',
  'Trump Save America Joint Fundraising Committee - Launchpad Strategies (TMA Direct)' : 'Trump Save America - TMA',
  'Ultra MAGA PAC - The Aventine Group (TMA Direct)' : 'Ultra MAGA PAC - TMA',
  'Van Drew' : 'Jeff Van Drew',
  'Van Drew for Congress - National Public Affairs (TMA Direct)' : 'Jeff Van Drew - TMA',
  'Van Orden' : 'Derrick Van Orden',
  'Virginians for Safe Communities (TMA Direct)' : 'Virginians for Safe Communities - TMA',
  'Vivek Ramaswamy for President (TMA Direct)' : 'Vivek Ramaswamy - TMA',
  'Wagner' : 'Ann Wagner',
  'Wesley Hunt (TMA)' : 'Wesley Hunt - TMA',
  'Wheeless, Tanya (AZ-09)' : 'Tanya Wheeless',
  'White (916)' : 'Dave White - TMA',
  'White Coat Waste' : 'White Coat Waste',
  'Williams, Brandon (NY-22)' : 'Brandon Williams',
  'WV GOP Inc - National Public Affairs (TMA Direct)' : 'WV GOP - TMA',
  'Yakym, Rudy (IN-02)' : 'Rudy Yakym',
  'Young Kim' : 'Young Kim',
  'Zinke, Ryan (MT-01)' : 'Ryan Zinke',
}

def external_account_name_to_internal_account_names(external_account_name: str) -> list[str]:
  return [ian for ian, ean in internal_account_name_to_external_account_name.items() if ean == external_account_name]

def external_account_names_to_internal_account_names_list_mapping(external_account_names: list[str]) -> list[str]:
  return [ian for ean in external_account_names for ian in external_account_name_to_internal_account_names(ean)]

def external_topic_names_to_internal_hooks_list_mapping(external_topic_names: list[str]) -> list[str]:
  return [topics_big[e]["internal name"]+"_hook" for e in external_topic_names]

def main() -> None:
  """This page performs a peculiar task known as "topic reporting", which is basically just summary statistics about various topic keywords (internally called "hooks").

  You must have streamlit installed to run this program. This script is usually run as part of Cicero run.bat in the main folder.

  List of derived quantities, left to right (does not include "topic", which is also there, but not derived per se):
    TV Funds: SUM of TV Funds
    FPM ($): SUM([TV_FUNDS]) / SUM([SENT]) * 1000
    ROAS (%): SUM([TV_FUNDS]) / SUM([SPEND_AMOUNT]) PERCENT
    Sent: SUM of Sent
    Result_Count: Count Distinct of Result Name
  """

  with st.expander("Topics..."):

    # Complicated logic just to have defaults and de/select all. Remember, the streamlit logic seems to be that the default value is overriden by user-selected values... unless the default value changes. Which makes sense, as these things go.
    # It's called an "opinion" and not a "state" because it doesn't directly mirror the state; it only changes when we need to change the state away from what the user has set. Thus, the program suddenly having an opinion about what should be selected, so to speak.
    #TODO: (urgent) whatever I did here, it's slightly wrong, because uhh sometimes when the user selects something just now and then clicks a button, the button doesn't override it. But another click of a button does it. So, I have to re-read the streamlit docs about this, because I guess my mental model (or code) is wrong.
    topics_gigaselect_default_selected = ["biden", "border", "deadline", "murica", "faith", "commie", "control_of_congress", "scotus", "economy", "election_integrity"]
    cols = st.columns(3)
    with cols[0]:
      if st.button("Select All"):
        st.session_state["topics_gigaselect_opinion"] = {t: True for t in topics_big}
    with cols[1]:
      if st.button("Deselect All"):
        st.session_state["topics_gigaselect_opinion"] = {t: False for t in topics_big}
    with cols[2]:
      if st.button("Reset To Default Selection") or not st.session_state.get("topics_gigaselect_opinion"): # set the haver of opinions up by default
        st.session_state["topics_gigaselect_opinion"] = {t: (topics_big[t]["internal name"] in topics_gigaselect_default_selected) for t in topics_big}

    topics_gigaselect = {}
    topic_check_cols = st.columns(len(topics_big)//14 + 1) #the items per column is chosen arbitrarily to kind of be good.
    for i, t in enumerate(topics_big): #In even cols, including 0, put a color square
      with topic_check_cols[i//14]:
        col1, col2 = st.columns([0.1, 0.9])
        with col1:
          color_code = topics_big[t]["color"]
          m = st.markdown(f' <div style="color:{color_code}" title="{t}, {color_code}">&#9632;</div>', unsafe_allow_html=True)
        with col2:
          topics_gigaselect[t] = st.checkbox(t, value=st.session_state["topics_gigaselect_opinion"][t])

  col1, col2, col3, col4 = st.columns(4) #possibly refactor this into non-unpacking for-loop type thing if I need to keep editing it.
  with col1:
    past_days = st.radio("Date range", [1, 7, 14, 30], index=1, format_func=lambda x: "Yesterday" if x == 1 else f"Last {x} days", help="The date range from which to display data. This will display data from any calendar day greater than or equal to (the present day minus the number of days specified). That is, 'Yesterday' will display data from both yesterday and today (and possibly, in rare circumstances, from the future).\n\nThis control only controls the top graph, and is never applied to the bottom graph.")
  with col2:
    accounts = st.multiselect("Account", ["(all)"]+load_account_names(), default="(all)", help="This control allows you to filter on the account name. If '(all)' is one of the selected values, all of the accounts will be presented.")
    accounts = external_account_names_to_internal_account_names_list_mapping(load_account_names() if "(all)" in accounts else accounts)
  with col3:
    project_type = st.selectbox("Project Type", ["Both", "Text Message", "Email"], index=0, help="This control allows you to filter on the project type, between email and text message. If Both selected, no filtering will be done.\n\n Internally, the filtering is done based on whether the project_type begins with \"\", \"Text Message\", or \"Email\".")
    if project_type == "Both":
      project_type = "" # this should match anything.
  with col4:
    askgoal = st.selectbox("Ask-Goal", ["Both", "Hard/Medium Ask", "Soft Ask/Listbuilding"], help='This control allows you to filter on \"ask type\" which is basically how directly focused on fundraising the text was supposed to be. Hard is more and soft is less.\n\nThe internal logic is that "Both" is no filter; "Soft Ask/Listbuilding" is (Goal = Fundraising AND Ask Type = Soft Ask) OR Goal = List Building; and "Hard/Medium Ask" is Goal = Fundraising AND Ask Type != Soft Ask. (`!= "Soft Ask"` is the same as `in ("Hard Ask", "Medium Ask")` except it will also catch the values null and \'None\', which are sometimes also in there.)')
    askgoal = str(askgoal or "Both") #appease typechecker by removing the optionality of this type
    askgoal_string = {"Both": "true", "Hard/Medium Ask": "GOAL = 'Fundraising' and FUNDRAISING_TYPE != 'Soft Ask'", "Soft Ask/Listbuilding": "GOAL = 'Fundraising' and FUNDRAISING_TYPE = 'Soft Ask' or GOAL = 'List Building'"}[askgoal]

  #To minimize RAM usage on the front end, most of the computation is done in the sql query, on the backend.
  #There's only really one complication to this data, which is that each row is duplicated n times — the "product" of the row and the list of hook types, as it were. Then only the true hooks have Hook_Bool true (all others have Hook_Bool null, which is our signal to ignore that row). This is just because it's easy to do a pivot table (or something) in Tableau that way; it doesn't actually matter. But we have to deal with it. It is also easy for us to deal with in SQL using WHERE Hook_Bool=true GROUP BY Hooks.
  summary_data_per_topic = sql_call(f"""WITH stats(topic, funds, sent, spend, project_count) AS (SELECT Hooks, SUM(TV_FUNDS), SUM(SENT), SUM(SPEND_AMOUNT), COUNT(DISTINCT PROJECT_NAME) FROM hook_reporting.default.hook_data_prod WHERE PROJECT_TYPE like '{project_type}%' and account_name in {to_sql_tuple_string(accounts)} and {askgoal_string} and SEND_DATE >= NOW() - INTERVAL {past_days} DAY and SEND_DATE < NOW() and Hooks in {to_sql_tuple_string(external_topic_names_to_internal_hooks_list_mapping(bool_dict_to_string_list(topics_gigaselect)))} and Hook_Bool=true GROUP BY Hooks) SELECT topic, funds, try_divide(funds, sent)*1000, try_divide(funds, spend)*100, project_count from stats""")
  key_of_rows = ("Topic", "Funds", "FPM ($)", "ROAS (%)", "Project count")

  dicted_rows = {key_of_rows[i]: [row[i] for row in summary_data_per_topic] for i, key in enumerate(key_of_rows)} #various formats probably work for this; this is just one of them.
  dicted_rows["color"] = [tb["color"] for t in dicted_rows["Topic"] for _, tb in topics_big.items() if tb["internal name"] == t.removesuffix("_hook")] #this logic is really grody
  if len(summary_data_per_topic):
    chart = alt.Chart(pd.DataFrame(dicted_rows)).mark_circle(size=90).encode(alt.X("ROAS (%)"), alt.Y("FPM ($)"), alt.Color("Topic", scale=alt.Scale(domain=dicted_rows["Topic"], range=dicted_rows["color"]), legend=None), tooltip=key_of_rows)
    st.altair_chart(chart, use_container_width=True)
  else:
    st.info("No data points are selected by the values indicated by the controls. Therefore, there is nothing to graph. Please broaden your criteria.")

  # Behold! Day (x) vs TV funds (y) line graph, per selected topic, which is what we decided was the only other important graph to keep from the old topic reporting application.
  topics = st.multiselect("Topics", topics_big, default="All", help="This control filters the below graph to only include results that have the selected topic.  If 'All' is one of the selected values, an aggregate sum of all the topics will be presented, as well.")
  topics = external_topic_names_to_internal_hooks_list_mapping(topics)
  search = st.text_input("Search", help="This box, if filled in, makes the below graph only include results that have text (in the clean_text or clean_email field) matching the contents of this box, as a regex (Java flavor regex; see https://regex101.com/?flavor=java&regex=biden|trump&flags=gm&testString=example%20non-matching%20text%0Asome%20trump%20stuff%0Abiden!%0Atrumpbiden for more details and to experiment interactively). This ***is*** case sensitive, and if you enter a regex that doesn't match any text appearing anywhere then the below graph might become nonsensical.") # Java flavor mentioned here: https://docs.databricks.com/en/sql/language-manual/functions/regexp.html # I've only seen the nonsensical graph (it's wrong axes) occur during testing, and haven't seen it in a while, but I guess it might still happen.
  if search:
    search_string = "(clean_email regexp %(regexp)s or clean_text regexp %(regexp)s)"
  else:
    search_string = "true"

  day_data_per_topic = sql_call(f"""WITH stats(date, funds, topic) AS (SELECT SEND_DATE, SUM(TV_FUNDS), Hooks FROM hook_reporting.default.hook_data_prod WHERE PROJECT_TYPE like '{project_type}%' and account_name in {to_sql_tuple_string(accounts)} and hooks in {to_sql_tuple_string(topics)} and {askgoal_string} and SEND_DATE >= NOW() - INTERVAL 30 DAY and SEND_DATE < NOW() and Hook_Bool=true and {search_string} GROUP BY SEND_DATE, Hooks) SELECT date, funds, topic from stats""", {"regexp": search})
  if len(day_data_per_topic):
    st.line_chart(to_graphable_dict(day_data_per_topic, "Day", "Funds ($)", "Topic"), x='Day', y='Funds ($)', color='Topic', height=500) #COULD: make colors match above. Not sure if it's important.
  else:
    st.info("No data points are selected by the values indicated by the controls. Therefore, there is nothing to graph. Please broaden your criteria.")
if __name__ == "__main__": main()
