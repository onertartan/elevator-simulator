  function circularGraphCustom(TRAFFIC)
        m=2;n=9;
        rt=TRAFFIC%{m,n}.Pr;
        
        figure
        % Create custom node labels
        myLabel = cell(length(rt));
        for i = 1:length(rt)
            myLabel{i} =[(num2str(i)) '. floor'];
        end
        % Create custom colormap
        myColorMap = lines(length(rt));
        circularGraph(rt,'Colormap',myColorMap,'Label',myLabel);
    end