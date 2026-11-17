package org.atomverse.pointengine;

import android.content.Context;
import android.graphics.*;
import android.view.MotionEvent;
import android.view.View;
import org.json.*;

/** Observer-only projection. Camera gestures never write to the mathematical kernel. */
public class EntityView extends View {
    private final Paint paint = new Paint(3);
    private JSONObject state = new JSONObject();
    public String mode = "sphere";
    private float yaw=.55f, pitch=.35f, lastX,lastY;
    public EntityView(Context context) { super(context); setContentDescription("Entity projection; drag to orbit camera"); }
    public void setState(JSONObject value) { state=value; invalidate(); }
    private float[] project(double x,double y,double z) {
        double u=x*Math.cos(yaw)-z*Math.sin(yaw), depth=x*Math.sin(yaw)+z*Math.cos(yaw);
        double v=y*Math.cos(pitch)-depth*Math.sin(pitch);
        double distance=20+depth*Math.cos(pitch)+y*Math.sin(pitch);
        float scale=(float)(Math.min(getWidth(),getHeight())/15.0*20/Math.max(2,distance));
        return new float[]{getWidth()/2f+(float)u*scale,getHeight()/2f-(float)v*scale,scale};
    }
    @Override protected void onDraw(Canvas c) {
        c.drawColor(Color.rgb(13,25,39)); paint.setShader(null); paint.setStyle(Paint.Style.STROKE); paint.setStrokeWidth(1);
        paint.setColor(Color.rgb(38,61,80));
        for(int i=-10;i<=10;i++) { line(c,project(i,0,-10),project(i,0,10)); line(c,project(-10,0,i),project(10,0,i)); }
        int[] colors={0xffff7272,0xff72df93,0xff80b6ff};
        for(int i=0;i<3;i++) { paint.setColor(colors[i]); float[] p=project(i==0?6:0,i==1?6:0,i==2?6:0); line(c,project(0,0,0),p); paint.setTextSize(24); c.drawText(new String[]{"X","Y","Z"}[i],p[0],p[1],paint); }
        if(!state.optBoolean("entity_active",true)) return;
        try {
            JSONArray pos=state.getJSONArray("position"), rgba=state.getJSONArray("color");
            int color=Color.argb((int)(255*rgba.getDouble(3)),(int)(255*rgba.getDouble(0)),(int)(255*rgba.getDouble(1)),(int)(255*rgba.getDouble(2)));
            paint.setColor(color); paint.setStrokeWidth(3);
            if(mode.equals("sphere")) {
                float[] p=project(pos.getDouble(0),pos.getDouble(1),pos.getDouble(2));
                float radius=Math.max(2,Math.min(800,(float)state.getDouble("radius")*p[2]));
                paint.setStyle(Paint.Style.FILL);
                int alpha=Color.alpha(color);
                paint.setShader(new RadialGradient(p[0]-radius*.3f,p[1]-radius*.3f,radius*1.4f,new int[]{Color.argb(alpha,255,255,255),color,Color.argb(alpha,9,16,28)},null,Shader.TileMode.CLAMP));
                c.drawCircle(p[0],p[1],radius,paint); paint.setShader(null);
            } else if(mode.equals("data")) {
                paint.setStyle(Paint.Style.FILL); paint.setTextSize(25);
                String[] rows={"XYZ "+pos,"t = "+state.optDouble("sim_time"),"f = "+state.optDouble("frequency"),"A = "+state.optDouble("amplitude"),"phase = "+state.optDouble("phase"),"signal = "+state.optDouble("oscillator_value")};
                for(int i=0;i<rows.length;i++) c.drawText(rows[i],20,35+i*32,paint);
            } else {
                Path path=new Path(); double f=state.optDouble("frequency"), phase=state.optDouble("phase"), a=state.optDouble("effective_amplitude",1), t=state.optDouble("oscillator_time");
                for(int i=0;i<=256;i++) { double u=i/256.0, angle=2*Math.PI*f*(t+u*2)+phase; float x,y;
                    if(mode.equals("spiral")) { x=getWidth()/2f+(float)(Math.cos(angle)*u*getHeight()*.4); y=getHeight()/2f+(float)(Math.sin(angle)*u*getHeight()*.4); }
                    else { x=(float)(u*getWidth()); y=getHeight()/2f-(float)(Math.sin(angle)*Math.min(a,5)*getHeight()*.08); }
                    if(i==0)path.moveTo(x,y); else path.lineTo(x,y);
                } c.drawPath(path,paint);
            }
        } catch(JSONException ignored) { }
    }
    private void line(Canvas c,float[] a,float[] b) { c.drawLine(a[0],a[1],b[0],b[1],paint); }
    @Override public boolean onTouchEvent(MotionEvent e) {
        if(e.getAction()==MotionEvent.ACTION_DOWN) {lastX=e.getX();lastY=e.getY();getParent().requestDisallowInterceptTouchEvent(true);return true;}
        if(e.getAction()==MotionEvent.ACTION_MOVE) {yaw+=(e.getX()-lastX)*.008f;pitch=Math.max(-1.4f,Math.min(1.4f,pitch+(e.getY()-lastY)*.008f));lastX=e.getX();lastY=e.getY();invalidate();return true;}
        if(e.getAction()==MotionEvent.ACTION_UP) {performClick();return true;} return true;
    }
    @Override public boolean performClick() {super.performClick();return true;}
}
