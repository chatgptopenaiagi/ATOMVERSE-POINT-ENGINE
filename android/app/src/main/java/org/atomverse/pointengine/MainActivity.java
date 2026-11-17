package org.atomverse.pointengine;

import android.app.Activity;
import android.os.*;
import android.graphics.Color;
import android.view.*;
import android.widget.*;
import com.chaquo.python.*;
import com.chaquo.python.android.AndroidPlatform;
import org.json.*;
import java.io.*;
import java.util.concurrent.*;

/** Thin native control surface. All entity commands go through the shared Python validator. */
public class MainActivity extends Activity {
    private final ExecutorService worker=Executors.newSingleThreadExecutor();
    private final Handler ui=new Handler(Looper.getMainLooper());
    private PyObject bridge;
    private EntityView projection;
    private TextView coordinates,status;
    private EditText x,y,z,radius,frequency,amplitude,phase;
    private Button teleport,relative,appearance,oscillator,pause,resume,replay,close;
    private Spinner representation,color;
    private volatile JSONObject snapshot=new JSONObject();
    private boolean ready=false,leaving=false,pollPending=false,verifying=false;
    private volatile boolean foreground=false;
    private int verificationStage=0;
    private int verificationWait=0;
    private JSONArray checks=new JSONArray();
    private long pausedTick;
    private double viewTime;
    private final Runnable poll=new Runnable(){public void run(){
        if(leaving)return;
        if(ready&&!pollPending){pollPending=true;worker.execute(()->{
            try {JSONObject value=new JSONObject(bridge.callAttr("snapshot").toString());ui.post(()->{snapshot=value;render();pollPending=false;});}
            catch(Exception e){ui.post(()->{status.setText("Engine error: "+e.getMessage());pollPending=false;});}
        });} ui.postDelayed(this,33);
    }};
    @Override public void onCreate(Bundle saved){super.onCreate(saved);
        LinearLayout page=new LinearLayout(this);page.setOrientation(1);page.setPadding(16,36,16,28);page.setBackgroundColor(Color.rgb(13,25,39));
        page.setOnApplyWindowInsetsListener((v,insets)->{page.setPadding(16,insets.getSystemWindowInsetTop()+12,16,insets.getSystemWindowInsetBottom()+8);return insets;});
        TextView title=text("ATOMVERSE · ONE ENTITY",21);page.addView(title);
        coordinates=text("Starting mathematical engine…",15);page.addView(coordinates);
        projection=new EntityView(this);page.addView(projection,new LinearLayout.LayoutParams(-1,0,1));
        representation=new Spinner(this);representation.setAdapter(new ArrayAdapter<String>(this,android.R.layout.simple_spinner_dropdown_item,new String[]{"sphere","wave","spiral","signal","data"}));
        representation.setOnItemSelectedListener(new android.widget.AdapterView.OnItemSelectedListener(){public void onNothingSelected(android.widget.AdapterView<?> p){} public void onItemSelected(android.widget.AdapterView<?> p,View v,int i,long id){projection.mode=representation.getSelectedItem().toString();projection.invalidate();}});
        page.addView(representation);
        ScrollView scroller=new ScrollView(this);LinearLayout controls=new LinearLayout(this);controls.setOrientation(1);scroller.addView(controls);page.addView(scroller,new LinearLayout.LayoutParams(-1,dp(275)));
        LinearLayout xyz=row(controls);x=field(xyz,"X","0");y=field(xyz,"Y","0");z=field(xyz,"Z","0");
        LinearLayout moves=row(controls);teleport=button(moves,"Teleport",()->send(position("teleport","position")));relative=button(moves,"Move by XYZ",()->send(position("translate","delta")));
        LinearLayout geometry=row(controls);radius=field(geometry,"Radius","0.5");color=new Spinner(this);color.setAdapter(new ArrayAdapter<String>(this,android.R.layout.simple_spinner_dropdown_item,new String[]{"Cyan","Blue","Red","Green","Transparent"}));geometry.addView(color,new LinearLayout.LayoutParams(0,-2,1));appearance=button(geometry,"Apply look",()->{
            try {double[][] palette={{.2,.85,1,1},{0,0,1,1},{1,.2,.2,1},{.2,1,.4,1},{.2,.85,1,.35}};JSONObject c=new JSONObject();c.put("action","appearance");c.put("radius",value(radius));c.put("color",new JSONArray(palette[color.getSelectedItemPosition()]));send(c);}catch(Exception e){error(e);}
        });
        LinearLayout osc=row(controls);frequency=field(osc,"Frequency","1");amplitude=field(osc,"Amplitude","1");phase=field(osc,"Phase","0");
        oscillator=button(controls,"Apply oscillator",()->{try{JSONObject c=new JSONObject();c.put("action","oscillator");c.put("enabled",true);c.put("frequency",value(frequency));c.put("amplitude",value(amplitude));c.put("phase",value(phase));send(c);}catch(Exception e){error(e);}});
        LinearLayout flow=row(controls);button(flow,"Helix",()->send(json("{\"action\":\"trajectory\",\"trajectory\":{\"kind\":\"helix\",\"duration\":10}}")));button(flow,"Line to XYZ",()->{try{JSONObject c=json("{\"action\":\"trajectory\",\"trajectory\":{\"kind\":\"line\",\"duration\":2}}");c.getJSONObject("trajectory").put("target",new JSONArray(new double[]{value(x),value(y),value(z)}));send(c);}catch(Exception e){error(e);}});
        LinearLayout transport=row(controls);pause=button(transport,"Pause",()->send(json("{\"action\":\"pause\"}")));resume=button(transport,"Resume",()->send(json("{\"action\":\"resume\"}")));button(transport,"Stop",()->send(json("{\"action\":\"stop\"}")));button(transport,"Reset",()->send(json("{\"action\":\"reset\"}")));
        LinearLayout memory=row(controls);replay=button(memory,"Replay history",()->task(()->{int count=bridge.callAttr("begin_replay").toInt();ui.post(()->status.setText("Replaying "+count+" recorded states"));}));button(memory,"Live",()->send(json("{\"action\":\"pause\"}")));close=button(memory,"Save and close",()->finish());
        status=text("Local SQLite history · AI is optional and not required",12);page.addView(status);setContentView(page);
        verifying=getIntent().getBooleanExtra("verify",false);
        worker.execute(()->{try{if(!Python.isStarted())Python.start(new AndroidPlatform(this));bridge=Python.getInstance().getModule("android_bridge");bridge.callAttr("start",getFilesDir().getAbsolutePath());if(!foreground)bridge.callAttr("background");ui.post(()->{if(leaving)return;ready=true;poll.run();if(verifying)ui.postDelayed(this::verify,800);else if(getIntent().getBooleanExtra("capture",false))ui.postDelayed(()->writeReport(null),500);});}catch(Exception e){ui.post(()->error(e));}});
    }
    private int dp(int x){return Math.round(x*getResources().getDisplayMetrics().density);}
    private TextView text(String value,int size){TextView t=new TextView(this);t.setText(value);t.setTextSize(size);t.setTextColor(Color.rgb(210,237,245));return t;}
    private LinearLayout row(LinearLayout parent){LinearLayout r=new LinearLayout(this);r.setOrientation(0);parent.addView(r);return r;}
    private EditText field(LinearLayout row,String hint,String value){LinearLayout column=new LinearLayout(this);column.setOrientation(1);column.addView(text(hint,12));EditText f=new EditText(this);f.setContentDescription(hint);f.setText(value);f.setSingleLine();f.setInputType(0x3002);column.addView(f,new LinearLayout.LayoutParams(-1,-2));row.addView(column,new LinearLayout.LayoutParams(0,-2,1));return f;}
    private Button button(LinearLayout parent,String label,Runnable action){Button b=new Button(this);b.setText(label);b.setTextSize(11);b.setOnClickListener(v->{try{action.run();}catch(Exception e){error(e);}});parent.addView(b,new LinearLayout.LayoutParams(parent.getOrientation()==0?0:-1,-2,parent.getOrientation()==0?1:0));return b;}
    private double value(EditText f){double v=Double.parseDouble(f.getText().toString());if(!Double.isFinite(v))throw new IllegalArgumentException("Enter a finite number");return v;}
    private JSONObject json(String value){try{return new JSONObject(value);}catch(Exception e){throw new IllegalArgumentException(e);}}
    private JSONObject position(String action,String field){try{JSONObject c=new JSONObject();c.put("action",action);c.put(field,new JSONArray(new double[]{value(x),value(y),value(z)}));return c;}catch(Exception e){throw new IllegalArgumentException(e);}}
    private void send(JSONObject command){task(()->bridge.callAttr("command",command.toString()));}
    private void task(Runnable action){if(!ready||leaving)return;worker.execute(()->{try{action.run();}catch(Exception e){ui.post(()->error(e));}});}
    private void error(Exception e){status.setText("Command not applied: "+e.getMessage());}
    private JSONObject state(){return snapshot.optJSONObject("state");}
    private void render(){try{JSONObject s=state();if(s==null)return;projection.setState(snapshot.getJSONObject("projection"));coordinates.setText("XYZ "+s.getJSONArray("position")+"   t "+String.format(java.util.Locale.ROOT,"%.3f",s.getDouble("sim_time"))+"\n"+s.getString("simulation_status")+" · "+(snapshot.getBoolean("replaying")?"RECORDED":"LIVE"));if(!verifying)status.setText("Local history: "+snapshot.getJSONObject("history").getInt("written")+" events · "+snapshot.getJSONObject("history").getInt("dropped_samples")+" dropped");}catch(Exception e){error(e);}}
    @Override protected void onPause(){foreground=false;super.onPause();task(()->bridge.callAttr("background"));}
    @Override protected void onResume(){foreground=true;super.onResume();task(()->bridge.callAttr("foreground"));}
    @Override protected void onNewIntent(android.content.Intent intent){super.onNewIntent(intent);setIntent(intent);if(intent.getBooleanExtra("capture",false))ui.postDelayed(()->writeReport(null),300);}
    @Override protected void onDestroy(){leaving=true;ui.removeCallbacksAndMessages(null);worker.execute(()->{try{if(bridge!=null)bridge.callAttr("close");android.util.Log.i("ATOMVERSE","CLEAN_SHUTDOWN");}catch(Exception e){android.util.Log.e("ATOMVERSE","SHUTDOWN_FAILED",e);}});worker.shutdown();super.onDestroy();}
    private void check(String name,boolean passed)throws Exception{JSONObject c=new JSONObject();c.put("name",name);c.put("passed",passed);checks.put(c);if(!passed)throw new AssertionError(name);}
    private void verify(){try{JSONObject s=state();if(s==null){ui.postDelayed(this::verify,200);return;}
        switch(verificationStage){
        case 0:check("single entity running",s.getBoolean("entity_active")&&s.getInt("tick")>0);x.setText("2");y.setText("-1");z.setText("3");teleport.performClick();break;
        case 1:check("absolute teleport",s.getJSONArray("position").getDouble(0)==2&&s.getJSONArray("position").getDouble(1)==-1);x.setText("1");y.setText("2");z.setText("-3");relative.performClick();break;
        case 2:check("relative movement",s.getJSONArray("position").getDouble(0)==3&&s.getJSONArray("position").getDouble(1)==1&&s.getJSONArray("position").getDouble(2)==0);radius.setText("1.25");color.setSelection(1);appearance.performClick();break;
        case 3:check("radius and color",s.getDouble("radius")==1.25&&s.getJSONArray("color").getDouble(2)==1);frequency.setText("2");amplitude.setText("3");phase.setText("0.25");oscillator.performClick();break;
        case 4:check("oscillator configuration",s.getDouble("frequency")==2&&s.getDouble("amplitude")==3&&s.getDouble("phase")==.25);pause.performClick();break;
        case 5:check("pause",s.getString("simulation_status").equals("PAUSED"));pausedTick=s.getLong("tick");viewTime=s.getDouble("sim_time");representation.setSelection(1);break;
        case 6:check("view switch independent",s.getLong("tick")==pausedTick&&s.getDouble("sim_time")==viewTime);representation.setSelection(2);break;
        case 7:representation.setSelection(3);break;
        case 8:representation.setSelection(4);break;
        case 9:representation.setSelection(0);resume.performClick();break;
        case 10:check("resume",s.getLong("tick")>pausedTick);replay.performClick();break;
        case 11:if(!snapshot.getBoolean("replaying")&&verificationWait++<30){ui.postDelayed(this::verify,200);return;}check("recorded replay",snapshot.getBoolean("replaying"));check("history committed",snapshot.getJSONObject("history").getInt("written")>0);writeReport(null);return;
        } verificationStage++;ui.postDelayed(this::verify,300);
    }catch(Throwable e){writeReport(e.toString());}}
    private void writeReport(String failure){worker.execute(()->{try{JSONObject report=new JSONObject();report.put("status",failure==null?"PASS":"FAIL");report.put("capture_id",getIntent().getStringExtra("capture_id"));report.put("error",failure);report.put("checks",checks);report.put("vectors",new JSONObject(bridge.callAttr("conformance").toString()));report.put("sqlite",new JSONObject(bridge.callAttr("integrity").toString()));report.put("snapshot",new JSONObject(bridge.callAttr("snapshot").toString()));report.put("abis",new JSONArray(java.util.Arrays.asList(Build.SUPPORTED_ABIS)));report.put("python",Python.getInstance().getModule("sys").get("version").toString());try(FileWriter f=new FileWriter(new File(getExternalFilesDir(null),"verification.json"))){f.write(report.toString(2));}android.util.Log.i("ATOMVERSE","VERIFICATION "+report.getString("status"));ui.post(()->{verifying=false;status.setText("Verification: "+(failure==null?"PASS":failure));});}catch(Exception e){android.util.Log.e("ATOMVERSE","VERIFY_FAILED",e);}});}
}
