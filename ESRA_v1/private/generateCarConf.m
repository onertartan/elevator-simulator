function CAR=generateCarConf(startData)

n_cars = startData.NCmin:startData.NCmax;
CAR =  cell(1,length(n_cars));
ncc=0;
for n_car = n_cars
    for parkAlgorithm = startData.parkAlgorithm
        
        ncc=ncc+1;
        for car_id=1:n_car
            cars(car_id) = Car(startData,car_id);
            cars(car_id)= setParkFloor(cars(car_id));
            
        end
        CAR{ncc} = cars ;
    end
    
end

function car =setParkFloor(car)
if car.parkAlgorithm == 2
    car.parkFloor=1;
end







